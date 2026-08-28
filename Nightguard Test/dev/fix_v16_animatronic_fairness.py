import json
import sys
sys.path.insert(0, ".")
from block_builder import new_block, var_ref, num_lit, str_lit, block_ref_value, block_ref_bool, check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
an_target = next(t for t in data["targets"] if t["name"] == "Animatronics")
an = an_target["blocks"]
stage_vars = next(t for t in data["targets"] if t["name"] == "Stage")["variables"]

# ===========================================================================
# Part 1: each `rng *` procedure clobbers its own position-tracking variable
# (`previous cam man`/`previous cam woman`/`previous cam woman2`) with this
# call's *pre-jitter target* immediately on entry, before the internal
# manlist/womanlist/woman2list random pick decides the *actual* final
# position. That variable is then used for two different things -- clearing
# the camlist slot the animatronic is leaving, and (read by the caller on
# the *next* call) computing the next relative move -- and by the time
# either happens it already holds the wrong value. `rng women` doesn't even
# attempt a clear step at all. Net effect: stale "occupied" markers pile up
# in camlist (worse for women1, which never clears), and the next-move
# reference point drifts from the animatronic's real position -- a hidden
# source of unequal presence between the three animatronics over a game.
#
# Fix (same shape in all three): move the "clear old slot" step to the very
# top of the procedure, using the tracking variable's value from *before*
# this call touches it (the animatronic's true incoming position), and move
# the tracking-variable update to *after* the new slot is marked, using the
# final post-jitter position. `rng women` is missing the clear step, so it's
# constructed fresh, matching the other two.
# ===========================================================================

# --- rng man: pure reorder, no new blocks -----------------------------------
# old: head -> [goto man=arg] -> [previous cam man=goto man] -> add -> add ->
#      [goto man=manlist[rand]] -> [mark new slot] -> [clear old slot] -> wait=0 -> ...
# new: head -> [clear old slot] -> [goto man=arg] -> add -> add ->
#      [goto man=manlist[rand]] -> [mark new slot] -> [previous cam man=goto man] -> wait=0 -> ...
HEAD_MAN = "b?"
SET_GOTO_MAN = "b@"
SET_PREV_MAN = "e_"          # previous cam man = goto man (move to after mark)
ADD1_MAN = "b["
MARK_MAN = "X"
CLEAR_MAN = "Y"              # clear old slot (move to top)
WAIT0_MAN = "fd"

assert an[HEAD_MAN]["next"] == SET_GOTO_MAN
assert an[SET_GOTO_MAN]["next"] == SET_PREV_MAN
assert an[MARK_MAN]["next"] == CLEAR_MAN
assert an[CLEAR_MAN]["next"] == WAIT0_MAN

an[HEAD_MAN]["next"] = CLEAR_MAN
an[CLEAR_MAN]["parent"] = HEAD_MAN
an[CLEAR_MAN]["next"] = SET_GOTO_MAN
an[SET_GOTO_MAN]["parent"] = CLEAR_MAN
an[SET_GOTO_MAN]["next"] = ADD1_MAN
an[ADD1_MAN]["parent"] = SET_GOTO_MAN
an[MARK_MAN]["next"] = SET_PREV_MAN
an[SET_PREV_MAN]["parent"] = MARK_MAN
an[SET_PREV_MAN]["next"] = WAIT0_MAN
an[WAIT0_MAN]["parent"] = SET_PREV_MAN

# --- rngwomen2: identical reorder -------------------------------------------
HEAD_W2 = "cd"
SET_GOTO_W2 = "ce"
SET_PREV_W2 = "fx"
ADD1_W2 = "cf"
MARK_W2 = "!"
CLEAR_W2 = "#"
WAIT0_W2 = "fG"

assert an[HEAD_W2]["next"] == SET_GOTO_W2
assert an[SET_GOTO_W2]["next"] == SET_PREV_W2
assert an[MARK_W2]["next"] == CLEAR_W2
assert an[CLEAR_W2]["next"] == WAIT0_W2

an[HEAD_W2]["next"] = CLEAR_W2
an[CLEAR_W2]["parent"] = HEAD_W2
an[CLEAR_W2]["next"] = SET_GOTO_W2
an[SET_GOTO_W2]["parent"] = CLEAR_W2
an[SET_GOTO_W2]["next"] = ADD1_W2
an[ADD1_W2]["parent"] = SET_GOTO_W2
an[MARK_W2]["next"] = SET_PREV_W2
an[SET_PREV_W2]["parent"] = MARK_W2
an[SET_PREV_W2]["next"] = WAIT0_W2
an[WAIT0_W2]["parent"] = SET_PREV_W2

# --- rng women: add the missing clear step, matching man/women2's shape ----
HEAD_W1 = "b{"
SET_GOTO_W1 = "b|"
SET_PREV_W1 = "fi"        # previous cam woman = goto women (move to after mark)
ADD1_W1 = "b}"
MARK_W1 = "Z"
WAIT0_W1 = "fr"
PREV_WOMAN_VAR_ID = "b@(l#~~#Hbql_I/G?OV2"   # "previous cam woman"

assert an[HEAD_W1]["next"] == SET_GOTO_W1
assert an[SET_GOTO_W1]["next"] == SET_PREV_W1
assert an[SET_PREV_W1]["next"] == ADD1_W1
assert an[MARK_W1]["next"] == WAIT0_W1

letter_id = new_block(an, "operator_letter_of", None,
                       {"LETTER": num_lit(4), "STRING": var_ref("previous cam woman", PREV_WOMAN_VAR_ID)},
                       tag="w1letter")
arg_id = new_block(an, "argument_reporter_string_number", None, {}, fields={"VALUE": ["goto", None]}, tag="w1arg")
clear_w1 = new_block(an, "data_replaceitemoflist", HEAD_W1,
                      {"INDEX": block_ref_value(letter_id, "1"), "ITEM": block_ref_value(arg_id, "CAM3")},
                      fields={"LIST": ["camlist", "aH(4E3xESYnTf3`u|U$Q"]}, tag="w1clear")
an[letter_id]["parent"] = clear_w1
an[arg_id]["parent"] = clear_w1

an[HEAD_W1]["next"] = clear_w1
an[clear_w1]["parent"] = HEAD_W1
an[clear_w1]["next"] = SET_GOTO_W1
an[SET_GOTO_W1]["parent"] = clear_w1
an[SET_GOTO_W1]["next"] = ADD1_W1
an[ADD1_W1]["parent"] = SET_GOTO_W1
an[MARK_W1]["next"] = SET_PREV_W1
an[SET_PREV_W1]["parent"] = MARK_W1
an[SET_PREV_W1]["next"] = WAIT0_W1
an[WAIT0_W1]["parent"] = SET_PREV_W1

check(an, "Animatronics (rng man/women/women2 fairness reorder)")
print("Part 1 (rng man, rng women, rngwomen2 position-tracking reorder) sanity OK.")

# ===========================================================================
# Part 2: randomize the initial spawn -- each animatronic's start camera
# becomes uniformly 1-of-8, independently, instead of the fixed CAM4/CAM3/
# CAM5 every game (which also always clustered the three spawn points in the
# CAM2-CAM4 band, since each rng procedure only jitters +/-1 from its target).
# ===========================================================================
SPAWN_MAN_CALL = "fQ"
SPAWN_WOMAN_CALL = "fR"
SPAWN_WOMAN2_CALL = "fS"
SPAWN_SITES = [
    (SPAWN_MAN_CALL, "r-g1dZQPC;`Y9-u?%Del", "CAM4"),
    (SPAWN_WOMAN_CALL, "=T~dCnn]%D8|1Ogz)Fgv", "CAM3"),
    (SPAWN_WOMAN2_CALL, "N7EtZ2@XYW,bp*6Hx;%7", "CAM5"),
]
for call_id, arg_id_key, old_literal in SPAWN_SITES:
    call_block = an[call_id]
    assert call_block["inputs"][arg_id_key] == [1, [10, old_literal]]
    rand_id = new_block(an, "operator_random", None, {"FROM": num_lit(1), "TO": num_lit(8)}, tag="spawnrand")
    join_id = new_block(an, "operator_join", call_id,
                         {"STRING1": str_lit("CAM"), "STRING2": block_ref_value(rand_id, "1")}, tag="spawnjoin")
    an[rand_id]["parent"] = join_id
    call_block["inputs"][arg_id_key] = block_ref_value(join_id, old_literal)

check(an, "Animatronics (randomized spawn)")
print("Part 2 (randomized initial spawn cameras) sanity OK.")

# ===========================================================================
# Part 3: `ai enabled` global variable + a "Toggle AI Mode" custom block
# (same procedures_definition/prototype/call shape as CamMenu's
# `toggle cam menu` from the previous pass) so movement can be paused for
# manual testing. Bound to `t` as well as being directly clickable in the
# editor.
# ===========================================================================
AI_ENABLED_VAR = "zNGaiEnabledVar01"
stage_vars[AI_ENABLED_VAR] = ["ai enabled", "1"]

TOGGLE_PROCCODE = "Toggle AI Mode"
TOGGLE_DEF_ID = "zNGtoggleaidef01"
TOGGLE_PROTO_ID = "zNGtoggleaiproto01"

set_off = new_block(an, "data_setvariableto", None, {"VALUE": str_lit("0")},
                     fields={"VARIABLE": ["ai enabled", AI_ENABLED_VAR]}, tag="aioff")
set_on = new_block(an, "data_setvariableto", None, {"VALUE": str_lit("1")},
                    fields={"VARIABLE": ["ai enabled", AI_ENABLED_VAR]}, tag="aion")
eq_id = new_block(an, "operator_equals", None,
                   {"OPERAND1": var_ref("ai enabled", AI_ENABLED_VAR), "OPERAND2": str_lit("1")}, tag="aieq")
toggle_ifelse = new_block(an, "control_if_else", TOGGLE_DEF_ID,
                           {"CONDITION": block_ref_bool(eq_id), "SUBSTACK": [2, set_off], "SUBSTACK2": [2, set_on]},
                           tag="aiifelse")
an[eq_id]["parent"] = toggle_ifelse
an[set_off]["parent"] = toggle_ifelse
an[set_on]["parent"] = toggle_ifelse

an[TOGGLE_DEF_ID] = {
    "opcode": "procedures_definition", "next": toggle_ifelse, "parent": None,
    "inputs": {"custom_block": [2, TOGGLE_PROTO_ID]}, "fields": {}, "shadow": False, "topLevel": True,
    "x": 1600, "y": 400,
}
an[TOGGLE_PROTO_ID] = {
    "opcode": "procedures_prototype", "next": None, "parent": TOGGLE_DEF_ID,
    "inputs": {}, "fields": {}, "shadow": False, "topLevel": False,
    "mutation": {"tagName": "mutation", "children": [], "proccode": TOGGLE_PROCCODE,
                 "argumentids": "[]", "argumentnames": "[]", "argumentdefaults": "[]", "warp": "false"},
}

TOGGLE_CALL_ID = "zNGtoggleaicall01"
KEY_T_HAT_ID = "zNGkeytHat01"
an[TOGGLE_CALL_ID] = {
    "opcode": "procedures_call", "next": None, "parent": KEY_T_HAT_ID,
    "inputs": {}, "fields": {}, "shadow": False, "topLevel": False,
    "mutation": {"tagName": "mutation", "children": [], "proccode": TOGGLE_PROCCODE, "argumentids": "[]", "warp": "false"},
}
an[KEY_T_HAT_ID] = {
    "opcode": "event_whenkeypressed", "next": TOGGLE_CALL_ID, "parent": None,
    "inputs": {}, "fields": {"KEY_OPTION": ["t", None]}, "shadow": False, "topLevel": True,
}

check(an, "Animatronics (AI toggle block)")
print("Part 3 (ai enabled variable + Toggle AI Mode block + key t hat) sanity OK.")

# ===========================================================================
# Part 4: gate the movement loop's three rng calls behind `ai enabled` so the
# toggle actually pauses movement (spawn and the end-of-game "one last move"
# stay ungated -- the toggle is for pausing a running game, not preventing
# spawn).
# ===========================================================================
LOOP_WAIT4 = "fV"
LOOP_CALL_MAN = "cn"

assert an[LOOP_WAIT4]["next"] == LOOP_CALL_MAN

gate_eq = new_block(an, "operator_equals", None,
                     {"OPERAND1": var_ref("ai enabled", AI_ENABLED_VAR), "OPERAND2": str_lit("1")}, tag="gateeq")
gate_if = new_block(an, "control_if", LOOP_WAIT4,
                     {"CONDITION": block_ref_bool(gate_eq), "SUBSTACK": [2, LOOP_CALL_MAN]}, tag="gateif")
an[gate_eq]["parent"] = gate_if
an[LOOP_CALL_MAN]["parent"] = gate_if
an[LOOP_WAIT4]["next"] = gate_if

check(an, "Animatronics (movement gated by ai enabled)")
print("Part 4 (movement loop gated) sanity OK.")

# ===========================================================================
# Part 5: bound the wandering random walk to CAM1-8.
#
# Fixing part 1 (previous cam X now genuinely tracks the animatronic's real
# position instead of getting clobbered back toward the caller's own target
# every call) has a real consequence: the movement loop now performs a
# *real* unbounded +/-2-per-tick random walk, and nothing ever clamped the
# result to the valid camera range. Over a normal-length game (tens of
# 4-second ticks) that walk's typical drift is much larger than the 8-wide
# valid range -- confirmed this wasn't just a test-harness artifact by
# reasoning about the variance of a +/-2 uniform step over ~100+ ticks. The
# *previous*, buggy tracking variable accidentally masked this by tending to
# drag positions back toward the caller's own recent target instead of truly
# wandering -- so this was always a latent bug, just hidden by the other one.
#
# Fix: wrap each raw candidate camera number with a mod-8 normalization,
# `(((raw - 1) mod 8) + 1)`, so it always resolves to a valid CAM1-8 no
# matter how far the random walk has drifted. Chose wrap-around over
# clamp-to-edge deliberately: clamping would pile extra probability onto
# CAM1/CAM8 (whichever edge the walk hits) which would undermine the actual
# "equal chance" goal of this fix; wrapping keeps the walk uniform over the
# 8 positions. Scratch's `mod` (confirmed via this project's own
# interpreter.py, which mirrors real Scratch's floored-mod semantics) always
# returns a non-negative result for a positive divisor, so this is safe for
# negative raw values too.
# ===========================================================================
RAW_ADD_IDS = [
    "cp",  # main loop: rng man
    "cq",  # main loop: rng women
    "cr",  # main loop: rngwomen2
    "ct",  # tail: rng man
    "cv",  # tail: rng women
    "cw",  # tail: rngwomen2
    # Each `rng *` procedure has its *own* second layer of +/-1 jitter
    # (the manlist/womanlist/woman2list mechanism, picking between
    # target-1 and target-2) which is completely separate from the
    # caller-side offset above and needs the same wrap -- confirmed this
    # is real, not just theoretical, by running the actual movement loop
    # through interpreter.py: with the caller-side wrap alone, a target
    # near the CAM1/CAM2 edge still produced "CAM0" from *this* inner
    # jitter, since target-2 can go below 1 with no wrap of its own.
    "e{",  # rng man: manlist target-1
    "e}",  # rng man: manlist target-2
    "fk",  # rng women: womanlist target-1
    "fm",  # rng women: womanlist target-2
    "fz",  # rngwomen2: woman2list target-1
    "fB",  # rngwomen2: woman2list target-2
]

wrapped = 0
for raw_id in RAW_ADD_IDS:
    raw_block = an[raw_id]
    assert raw_block["opcode"] == "operator_add"
    join_id = raw_block["parent"]
    assert an[join_id]["opcode"] == "operator_join"
    old_string2 = an[join_id]["inputs"]["STRING2"]
    assert old_string2[1] == raw_id

    sub_id = new_block(an, "operator_subtract", None,
                        {"NUM1": block_ref_value(raw_id, "0"), "NUM2": num_lit(1)}, tag="wrapsub")
    mod_id = new_block(an, "operator_mod", None,
                        {"NUM1": block_ref_value(sub_id, "0"), "NUM2": num_lit(8)}, tag="wrapmod")
    add1_id = new_block(an, "operator_add", join_id,
                         {"NUM1": block_ref_value(mod_id, "0"), "NUM2": num_lit(1)}, tag="wrapadd1")
    an[sub_id]["parent"] = mod_id
    an[mod_id]["parent"] = add1_id
    an[raw_id]["parent"] = sub_id

    an[join_id]["inputs"]["STRING2"] = block_ref_value(add1_id, old_string2[2][1])
    wrapped += 1

check(an, "Animatronics (movement wrapped to CAM1-8)")
print(f"Part 5 (wrapped {wrapped} movement expressions to CAM1-8) sanity OK.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v16) written.")
