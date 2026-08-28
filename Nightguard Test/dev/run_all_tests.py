import json
import sys
sys.path.insert(0, ".")
from interpreter import Interpreter

PROJECT_PATH = "nightguard_extract/project.json"
data = json.load(open(PROJECT_PATH, encoding="utf-8"))

LEFT_CLICK_HAT = "bLmg7{PQ|g!kc$VSIpwg"
RIGHT_IFELSE = "DS-(O!4uIDa^*g|alQ4*"
OFFICE_RIGHT_DOOR_HAT = "@d:QNjylxkr!=i8wi.IU"
OFFICE_LEFT_DOOR_HAT = "q)l{oaAIG!/m`]/Ehz|x"
POWER_HAT = "Pa$?2%*%h(IEva$tWE3d"
TIME_HAT = "D=1DkwO6c;:s|9$yQ?!g"
JUMPSCARE_GATE_HAT = "mQx}93w6i5M9@.Wk_F1{"
ANIM_CHAIN_A_HEAD = "hSF;/i@ENoj*[sf]GF{i"
ANIM_LOOP_BLOCK = "fmgy/ot~2Iw+fvISEq[:"

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


for start, closed in [("95%", False), ("95%", True), ("10%", False), ("10%", True), ("1%", True), ("2%", False)]:
    final, ticks = run_power(start, closed)
    check(f"Power reaches exactly 0% (start={start} closed={closed})", final == "0%", f"-> {final}, {ticks} outer ticks")

_, ticks_open = run_power("20%", False)
_, ticks_closed = run_power("20%", True)
check("Door-closed drains at ~2x rate", ticks_closed == ticks_open // 2, f"open={ticks_open} closed={ticks_closed}")

# ---------------------------------------------------------------
# 3) Time cycling
# ---------------------------------------------------------------
interp = Interpreter(data)
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

print()
if failures:
    print(f"{len(failures)} FAILURE(S):", failures)
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
