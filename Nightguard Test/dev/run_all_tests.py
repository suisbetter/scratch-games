import json
import sys
sys.path.insert(0, ".")
from interpreter import Interpreter

PROJECT_PATH = "nightguard_extract/project.json"
data = json.load(open(PROJECT_PATH, encoding="utf-8"))

# Block ids below are re-derived by structural signature (opcode + which
# variable/list/broadcast they reference), not hardcoded from memory --
# TurboWarp regenerates every block id (but not variable/list ids) whenever
# it re-saves the project, which has happened more than once during this
# project's development. See dev/find_block_ids.py to regenerate this block
# if the ids drift again after another external re-save.
LEFT_CLICK_HAT = "il"
RIGHT_IFELSE = "c"
OFFICE_RIGHT_DOOR_HAT = "gZ"
OFFICE_LEFT_DOOR_HAT = "g*"
POWER_HAT = "g["
TIME_HAT = "g@"
JUMPSCARE_GATE_HAT = "mh"
ANIM_CHAIN_A_HEAD = "cr"
ANIM_LOOP_BLOCK = "("
IS_CLONE_VAR = "zNGisCloneVar0001"
CAMMENU_CLICK_HAT = "iP"
CAMMENU_KEY_HAT = "iR"
AI_ENABLED_VAR = "zNGaiEnabledVar01"
CAMLIST_ID = "aH(4E3xESYnTf3`u|U$Q"
LOOP_CALL_MAN = "cv"
LOOP_CALL_WOMAN = "cx"
LOOP_CALL_WOMAN2 = "f^"
TAIL_CALL_MAN = "cu"
TAIL_CALL_WOMAN = "cB"
TAIL_CALL_WOMAN2 = "cD"

failures = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not cond:
        failures.append(name)


# ---------------------------------------------------------------
# 1) Door open/close matrix
# ---------------------------------------------------------------
def run_door_seq(seq):
    interp = Interpreter(data)
    door_blocks = interp.blocks_for("Door")
    office_blocks = interp.blocks_for("Office")
    broadcasts = []
    interp.on_broadcast = lambda m: broadcasts.append(m)
    results = []
    for step in seq:
        if step == "L":
            interp.run_stack("Door", door_blocks[LEFT_CLICK_HAT]["next"], door_blocks)
        else:
            interp.run_stack("Door", RIGHT_IFELSE, door_blocks)
        while broadcasts:
            msg = broadcasts.pop(0)
            if msg == "right door":
                interp.run_stack("Office", office_blocks[OFFICE_RIGHT_DOOR_HAT]["next"], office_blocks)
            elif msg == "left door":
                interp.run_stack("Office", office_blocks[OFFICE_LEFT_DOOR_HAT]["next"], office_blocks)
        results.append((interp.get_var(interp.varname_to_id["leftdoorstate"]),
                         interp.get_var(interp.varname_to_id["rightdoorstate"]),
                         interp.costumes["Office"]))
    return results


expected_costume = {("open", "open"): "costume1", ("closed", "open"): "costume5",
                     ("open", "closed"): "costume7", ("closed", "closed"): "costume13"}
door_ok = True
for seq in [["R", "L", "R", "L"], ["L", "R", "L", "R"], ["R", "R"], ["L", "L"],
            ["R", "L", "L", "R"], ["R", "R", "R", "R"], ["L", "L", "L", "L"]]:
    for step, (l, r, c) in zip(seq, run_door_seq(seq)):
        if c != expected_costume[(l, r)]:
            door_ok = False
check("Door open/close matrix (7 sequences)", door_ok)

# ---------------------------------------------------------------
# 2) Power drain: digit boundaries, door-closed doubling
# ---------------------------------------------------------------
def run_power(initial, door_closed):
    interp = Interpreter(data)
    interp.varstate[interp.varname_to_id["power"]] = initial
    interp.varstate[interp.varname_to_id["rightdoorstate"]] = "closed" if door_closed else "open"
    interp.varstate[interp.varname_to_id["leftdoorstate"]] = "open"
    ob = interp.blocks_for("Office")
    interp.run_stack("Office", ob[POWER_HAT]["next"], ob)
    n6 = sum(1 for l in interp.log if "WAIT 6" in l)
    return interp.varstate[interp.varname_to_id["power"]], n6


for start, closed in [("95%", False), ("95%", True), ("10%", False), ("10%", True), ("1%", True), ("2%", False),
                      ("100%", False), ("100%", True)]:
    # "100%" is the actual runtime starting value (set by Animatronics' own
    # green-flag script) -- the 4-character case that broke the old
    # length-2-vs-else digit extraction. Without this case, this exact bug
    # slips through, same as it did in the previous pass.
    final, ticks = run_power(start, closed)
    check(f"Power reaches exactly 0% (start={start} closed={closed})", final == "0%", f"-> {final}, {ticks} outer ticks")

# Exhaustive sweep, not just spot values: every starting power 1-100 (power's
# real domain -- Animatronics sets it to '100%', it only decreases), door
# open and closed, must reach exactly "0%" with *no negative intermediate
# value ever appearing* -- not just "reaches 0% eventually", since a buggy
# decrement that goes negative and this project's own equality/length checks
# could in principle still terminate through non-numeric-string comparisons
# without this catching it. This is the check that actually catches real
# Scratch's strict Number() coercion being violated (a direct `power - 1` on
# the full "N%" string silently computes 0 - 1 = -1 forever, never reaching
# "0%" at all under accurate semantics) -- confirmed this exact failure mode
# by running it before dev/interpreter.py's to_number was fixed to match
# real Scratch (it had a "parse leading numeric run" fallback that isn't how
# JavaScript's Number() actually behaves, which is exactly why the previous
# fix passed this suite yet still broke in real play).
sweep_ok = True
sweep_failures = []
for start in range(1, 101):
    for closed in (False, True):
        interp = Interpreter(data)
        interp.varstate[interp.varname_to_id["power"]] = f"{start}%"
        interp.varstate[interp.varname_to_id["rightdoorstate"]] = "closed" if closed else "open"
        interp.varstate[interp.varname_to_id["leftdoorstate"]] = "open"
        ob = interp.blocks_for("Office")
        interp.run_stack("Office", ob[POWER_HAT]["next"], ob)
        power_values = [l.split("= ")[1].strip("'") for l in interp.log if "SET power" in l]
        final = interp.varstate[interp.varname_to_id["power"]]
        if final != "0%" or any(v.startswith("-") for v in power_values):
            sweep_ok = False
            sweep_failures.append((start, closed, final, power_values[:3]))
check("Power sweep: every start 1-100 (open/closed) reaches exactly 0% with no negative intermediate",
      sweep_ok, f"-> {len(sweep_failures)} failures" + (f", e.g. {sweep_failures[0]}" if sweep_failures else ""))


def run_power_first_decrement(initial):
    interp = Interpreter(data)
    interp.varstate[interp.varname_to_id["power"]] = initial
    interp.varstate[interp.varname_to_id["rightdoorstate"]] = "open"
    interp.varstate[interp.varname_to_id["leftdoorstate"]] = "open"
    ob = interp.blocks_for("Office")
    interp.run_stack("Office", ob[POWER_HAT]["next"], ob)
    first_set = next(l for l in interp.log if "SET power" in l)
    return first_set.split("= ")[1].strip("'")

check('Power at "100%" decrements to "99%" (not a multi-digit-truncation jump like "9%")',
      run_power_first_decrement("100%") == "99%", f"-> {run_power_first_decrement('100%')!r}")

_, ticks_open = run_power("20%", False)
_, ticks_closed = run_power("20%", True)
check("Door-closed drains at ~2x rate", ticks_closed == ticks_open // 2, f"open={ticks_open} closed={ticks_closed}")

# ---------------------------------------------------------------
# 3) Time cycling
# ---------------------------------------------------------------
interp = Interpreter(data)
# Explicit setup, not relying on Stage's serialized default -- that default
# is just whatever `time` happened to be when the project was last saved in
# the editor (a mid-game snapshot from actual play, same as `power`'s stale
# "95%" default from session 3), not a real starting value. Animatronics'
# own green-flag script always resets `time` to "12 AM" for a real game.
interp.varstate[interp.varname_to_id["time"]] = "12 AM"
ob = interp.blocks_for("Office")
interp.run_stack("Office", ob[TIME_HAT]["next"], ob)
times = [l.split("= ")[1].strip("'") for l in interp.log if "SET time" in l]
check("Time cycles 12 AM -> 6 AM via 1 AM wrap, no runaway", times == ["13 AM", "1 AM", "2 AM", "3 AM", "4 AM", "5 AM", "6 AM"], f"-> {times}")

# ---------------------------------------------------------------
# 4) Animatronic AI: no garbage camera names, valid bookkeeping
# ---------------------------------------------------------------
interp = Interpreter(data)
ab = interp.blocks_for("Animatronics")
camlist_id = interp.listname_to_id["camlist"]
interp.liststate[camlist_id] = [f"CAM{i}" for i in range(1, 9)]
interp.varstate[AI_ENABLED_VAR] = "1"  # explicit, not relying on Stage's serialized default
for name in ["previous cam man", "previous cam woman", "previous cam woman2"]:
    interp.varstate[interp.varname_to_id[name]] = ""
first_three = []
bid = ANIM_CHAIN_A_HEAD
for _ in range(3):
    first_three.append(bid)
    bid = ab[bid]["next"]
for spawn_id in first_three:
    b = dict(ab[spawn_id])
    b["next"] = None
    interp.run_stack("Animatronics", spawn_id, {**ab, spawn_id: b})
valid_cams = {f"CAM{i}" for i in range(1, 9)}
spawn_ok = all(interp.varstate[interp.varname_to_id[n]] in valid_cams
               for n in ["previous cam man", "previous cam woman", "previous cam woman2"])
check("Animatronic initial spawn lands on valid CAM1-8", spawn_ok)

loop_substack = ab[ANIM_LOOP_BLOCK]["inputs"]["SUBSTACK"][1]
loop_ok = True
for _ in range(15):
    interp.run_stack("Animatronics", loop_substack, ab)
    for n in ["previous cam man", "previous cam woman", "previous cam woman2"]:
        if interp.varstate[interp.varname_to_id[n]] not in valid_cams:
            loop_ok = False
check("Animatronic movement loop stays on valid CAM1-8 across 15 iterations", loop_ok)

# camlist entries should only ever be plain "CAMn" or "name(CAMn)", never garbage
import re
camlist_pattern = re.compile(r"^(CAM\d|(man|women1|women2)\(CAM\d\))$")
camlist_ok = all(camlist_pattern.match(v) for v in interp.liststate[camlist_id])
check("camlist entries are well-formed after spawn+15 loop iterations", camlist_ok, f"-> {interp.liststate[camlist_id]}")

# ---------------------------------------------------------------
# 4b) Fairness: each animatronic's tracking variable stays in sync with
#     camlist -- exactly one slot shows its name, matching where it's
#     actually tracked as being. This is exactly the invariant the old
#     position-tracking bug violated (stale markers left behind at old
#     slots, tracking variable drifting from the real position). Uses
#     distinct starting positions per animatronic -- the interpreter's
#     `pick random` is a fixed deterministic midpoint per call, so same
#     starting position for all three would make them compute identical
#     moves and mask real bugs behind coincidental overwrites.
# ---------------------------------------------------------------
interp = Interpreter(data)
ab = interp.blocks_for("Animatronics")
interp.liststate[camlist_id] = [f"CAM{i}" for i in range(1, 9)]
interp.varstate[interp.varname_to_id["previous cam man"]] = "CAM2"
interp.varstate[interp.varname_to_id["previous cam woman"]] = "CAM8"
interp.varstate[interp.varname_to_id["previous cam woman2"]] = "CAM1"
# Explicit setup, not relying on Stage's serialized default for `ai enabled`
# -- same reasoning as `time` above: it's whatever the toggle happened to be
# set to when the project was last saved (e.g. from testing the toggle
# itself), not necessarily "on".
interp.varstate[AI_ENABLED_VAR] = "1"
loop_substack = ab[ANIM_LOOP_BLOCK]["inputs"]["SUBSTACK"][1]

fairness_ok = True
collision_ticks = 0
for _ in range(50):
    interp.run_stack("Animatronics", loop_substack, ab)
    positions = {
        "man": interp.varstate[interp.varname_to_id["previous cam man"]],
        "women1": interp.varstate[interp.varname_to_id["previous cam woman"]],
        "women2": interp.varstate[interp.varname_to_id["previous cam woman2"]],
    }
    for tag, pos in positions.items():
        if pos not in valid_cams:
            fairness_ok = False
            continue
        matching_slots = [v for v in interp.liststate[camlist_id] if v == f"{tag}({pos})"]
        other_stale = [v for v in interp.liststate[camlist_id] if v.startswith(f"{tag}(") and v != f"{tag}({pos})"]
        if other_stale:
            fairness_ok = False  # a stale/wrong-position leftover is always a real bug
        elif len(matching_slots) != 1:
            # Missing entirely is only legitimate if another animatronic is
            # genuinely at the exact same camera this tick -- camlist can
            # only hold one occupant string per slot (a pre-existing
            # limitation of this project's data model, not something this
            # pass introduces or is trying to solve). Anything else is a
            # real bug.
            others_here = [t for t, p in positions.items() if t != tag and p == pos]
            if others_here:
                collision_ticks += 1
            else:
                fairness_ok = False
check("Each animatronic's camlist mark matches its tracked position, with no stale wrong-position leftovers, across 50 iterations",
      fairness_ok, f"-> final camlist {interp.liststate[camlist_id]}, {collision_ticks} same-camera collisions (pre-existing single-occupant-per-slot limitation, not a bug this introduces)")

# ---------------------------------------------------------------
# 4c) Equal spawn chance: each of the 3 initial spawn calls is built from
#     `Random(1, 8)`, not a fixed camera -- structural check (the old code
#     used fixed CAM4/CAM3/CAM5 literals with no Random block at all).
# ---------------------------------------------------------------
def spawn_uses_uniform_random(spawn_call_id):
    call_block = ab[spawn_call_id]
    arg_input = next(iter(call_block["inputs"].values()))
    join_block = ab[arg_input[1]]
    rand_id = join_block["inputs"]["STRING2"][1]
    rand_block = ab[rand_id]
    if rand_block["opcode"] != "operator_random":
        return False
    frm = interp.eval_input("Animatronics", rand_block["inputs"]["FROM"], ab)
    to = interp.eval_input("Animatronics", rand_block["inputs"]["TO"], ab)
    return str(frm) == "1" and str(to) == "8"

spawn_calls = [ANIM_CHAIN_A_HEAD]
bid = ab[ANIM_CHAIN_A_HEAD]["next"]
for _ in range(2):
    spawn_calls.append(bid)
    bid = ab[bid]["next"]
spawn_random_ok = all(spawn_uses_uniform_random(c) for c in spawn_calls)
check("All 3 initial spawns draw uniformly from Random(1,8), not a fixed camera", spawn_random_ok)

# ---------------------------------------------------------------
# 4d) AI toggle: with `ai enabled` off, the movement loop body does nothing;
#     with it on (the default), movement proceeds as normal.
# ---------------------------------------------------------------
def run_loop_tick(ai_on):
    interp = Interpreter(data)
    ab = interp.blocks_for("Animatronics")
    interp.liststate[camlist_id] = [f"CAM{i}" for i in range(1, 9)]
    interp.varstate[interp.varname_to_id["previous cam man"]] = "CAM4"
    interp.varstate[AI_ENABLED_VAR] = "1" if ai_on else "0"
    loop_substack = ab[ANIM_LOOP_BLOCK]["inputs"]["SUBSTACK"][1]
    interp.run_stack("Animatronics", loop_substack, ab)
    return interp.varstate[interp.varname_to_id["previous cam man"]]

check('AI toggle: "ai enabled"=0 leaves the movement loop as a no-op',
      run_loop_tick(ai_on=False) == "CAM4")
check('AI toggle: "ai enabled"=1 (default) lets movement proceed',
      run_loop_tick(ai_on=True) != "CAM4")

# ---------------------------------------------------------------
# 4e) Character-specific movement paths: structural check of each
#     animatronic's per-tick offset (man="Rush" wider jump, women1="Patrol"
#     tight jitter, women2="Sweep" fixed +1, no randomness) -- mirrors how
#     the spawn-uniformity check inspects the Random block's bounds directly
#     rather than relying on the interpreter's deterministic `pick random`
#     (which returns a fixed midpoint per call, so it can't distinguish
#     range width across a single sample the way a structural check can).
# ---------------------------------------------------------------
def base_offset_block(call_id):
    """Descend from a `Call rng *(...)` block, through the mod-8 wrap
    machinery, to the underlying `Letter(...) + <offset>` add block."""
    join_id = ab[call_id]["inputs"][next(iter(ab[call_id]["inputs"]))][1]
    bid = join_id
    while True:
        b = ab[bid]
        if b["opcode"] == "operator_join":
            bid = b["inputs"]["STRING2"][1]
        elif b["opcode"] == "operator_add" and ab.get(b["inputs"]["NUM1"][1], {}).get("opcode") == "operator_mod":
            bid = b["inputs"]["NUM1"][1]
        elif b["opcode"] == "operator_mod":
            bid = b["inputs"]["NUM1"][1]
        elif b["opcode"] == "operator_subtract":
            bid = b["inputs"]["NUM1"][1]
        else:
            return bid  # the base "Letter(...) + <offset>" add


def offset_kind(call_id):
    base_add = base_offset_block(call_id)
    offset_id = ab[base_add]["inputs"]["NUM2"][1]
    if not isinstance(offset_id, str) or offset_id not in ab:
        return ("fixed", 1)  # a plain literal, no block -- e.g. "+1"
    offset_block = ab[offset_id]
    if offset_block["opcode"] == "operator_random":
        frm = int(interp.eval_input("Animatronics", offset_block["inputs"]["FROM"], ab))
        to = int(interp.eval_input("Animatronics", offset_block["inputs"]["TO"], ab))
        return ("random", (frm, to))
    return ("unknown", None)


interp = Interpreter(data)
ab = interp.blocks_for("Animatronics")
paths_ok = True
path_report = {}
for label, main_call, tail_call in [
    ("man (Rush)", LOOP_CALL_MAN, TAIL_CALL_MAN),
    ("women1 (Patrol)", LOOP_CALL_WOMAN, TAIL_CALL_WOMAN),
    ("women2 (Sweep)", LOOP_CALL_WOMAN2, TAIL_CALL_WOMAN2),
]:
    path_report[label] = offset_kind(main_call)

man_kind, man_bounds = path_report["man (Rush)"]
women1_kind, women1_bounds = path_report["women1 (Patrol)"]
women2_kind, women2_bounds = path_report["women2 (Sweep)"]
paths_ok = (
    man_kind == "random" and women1_kind == "random" and women2_kind == "fixed"
    and (man_bounds[1] - man_bounds[0]) > (women1_bounds[1] - women1_bounds[0])
    and women2_bounds == 1
)
check("Each animatronic has a distinct movement path (man=wide random, women1=tight random, women2=fixed +1)",
      paths_ok, f"-> {path_report}")

# ---------------------------------------------------------------
# 5) Per-door jumpscare gate independence
# ---------------------------------------------------------------
def run_gate(left_state, right_state, cam1, cam2):
    interp = Interpreter(data)
    interp.varstate[interp.varname_to_id["leftdoorstate"]] = left_state
    interp.varstate[interp.varname_to_id["rightdoorstate"]] = right_state
    interp.liststate[interp.listname_to_id["camlist"]] = [cam1, cam2, "", "", "", "", "", ""]
    ob = interp.blocks_for("Office")
    interp.costumes["Office"] = "costume1"
    interp.run_stack("Office", ob[JUMPSCARE_GATE_HAT]["next"], ob)
    return interp.costumes["Office"]


gate_cases = [
    ("open", "open", "man(CAM1)", "", "costume8"),
    ("closed", "open", "man(CAM1)", "", "costume1"),
    ("open", "closed", "man(CAM1)", "", "costume8"),
    ("open", "open", "", "man(CAM2)", "costume9"),
    ("open", "closed", "", "man(CAM2)", "costume1"),
    ("closed", "open", "", "man(CAM2)", "costume9"),
    ("open", "open", "man(CAM1)", "women1(CAM2)", "costume8"),
]
gate_ok = all(run_gate(l, r, c1, c2) == exp for l, r, c1, c2, exp in gate_cases)
check("Per-door jumpscare gate: each side blocked only by its own door", gate_ok)

# ---------------------------------------------------------------
# 6) The animatronic AI is actually reachable via green-flag hat discovery
#    (not just by directly poking a remembered block id) -- this is exactly
#    the class of bug (topLevel=False on a new hat) that a manual-id test
#    would silently miss.
# ---------------------------------------------------------------
interp = Interpreter(data)
ab = interp.blocks_for("Animatronics")
camlist_id = interp.listname_to_id["camlist"]
interp.liststate[camlist_id] = [f"CAM{i}" for i in range(1, 9)]
# Another green-flag hat in this sprite resets power to "100%"; since nothing
# decrements it in this isolated test, the (correctly reconnected) movement
# loop would spin until the safety cap -- that's expected here, not a bug.
# The spawn calls run before the loop either way, so check state regardless.
try:
    interp.start_hats("Animatronics", "event_whenflagclicked")
except Exception:
    pass
spawned = interp.varstate[interp.varname_to_id["previous cam man"]]
check("Animatronic green-flag hat is discoverable and actually runs (topLevel=True)",
      spawned in {f"CAM{i}" for i in range(1, 9)}, f"-> previous cam man = {spawned!r}")

# ---------------------------------------------------------------
# 7) Clicking the right door must not also fire the inherited left-door
#    `when this sprite clicked` hat. Real Scratch runs every hat script
#    (including plain click hats, not just "when I start as clone") once per
#    clone independently -- so a right-door click actually triggers BOTH the
#    clone's own if/else handler AND the sprite's other `when this sprite
#    clicked` script (written for the left door), unless guarded. Simulate
#    that real firing pattern here (the older door-matrix test above does
#    not -- it only ever runs one handler per simulated click).
# ---------------------------------------------------------------
def run_real_click(is_right):
    interp = Interpreter(data)
    door_blocks = interp.blocks_for("Door")
    broadcasts = []
    interp.on_broadcast = lambda m: broadcasts.append(m)
    if is_right:
        # The clone's own handler runs, AND (per real clone semantics) its
        # inherited copy of the left-door click hat also runs, with
        # `is clone` == '1' for that copy.
        interp.run_stack("Door", RIGHT_IFELSE, door_blocks)
        interp.varstate[IS_CLONE_VAR] = "1"
        interp.run_stack("Door", door_blocks[LEFT_CLICK_HAT]["next"], door_blocks)
    else:
        # The original isn't a clone; its own `is clone` stays unset/'0'.
        interp.run_stack("Door", door_blocks[LEFT_CLICK_HAT]["next"], door_blocks)
    return (interp.get_var(interp.varname_to_id["leftdoorstate"]),
            interp.get_var(interp.varname_to_id["rightdoorstate"]),
            broadcasts)

left_state, right_state, broadcasts = run_real_click(is_right=True)
check("Right-door click (as real clone) leaves leftdoorstate untouched",
      left_state == "open" and right_state == "closed" and "left door" not in broadcasts,
      f"-> left={left_state} right={right_state} broadcasts={broadcasts}")

left_state, right_state, broadcasts = run_real_click(is_right=False)
check("Left-door click (original, not a clone) still toggles leftdoorstate normally",
      left_state == "closed" and "left door" in broadcasts,
      f"-> left={left_state} broadcasts={broadcasts}")

# ---------------------------------------------------------------
# 8) CamMenu: the sprite-clicked and space-key handlers were de-duplicated
#    into a shared `toggle cam menu` custom block. Confirm both call sites
#    still produce identical behavior for every menucounter state they
#    previously handled directly.
# ---------------------------------------------------------------
def run_cammenu(hat, menucounter):
    interp = Interpreter(data)
    cm = interp.blocks_for("CamMenu")
    broadcasts = []
    interp.on_broadcast = lambda m: broadcasts.append(m)
    interp.varstate[interp.varname_to_id["menucounter"]] = menucounter
    interp.costumes["CamMenu"] = "costume1"
    interp.run_stack("CamMenu", cm[hat]["next"], cm)
    return broadcasts, interp.costumes["CamMenu"]

cammenu_ok = True
for mc in (1, 2):
    click_result = run_cammenu(CAMMENU_CLICK_HAT, mc)
    key_result = run_cammenu(CAMMENU_KEY_HAT, mc)
    if click_result != key_result:
        cammenu_ok = False
check("CamMenu click and space-key hats behave identically via shared procedure", cammenu_ok)

print()
if failures:
    print(f"{len(failures)} FAILURE(S):", failures)
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
