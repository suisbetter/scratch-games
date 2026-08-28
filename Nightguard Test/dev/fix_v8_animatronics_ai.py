import json
import sys
sys.path.insert(0, ".")
from block_builder import new_block, check as bb_check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
anim = next(t for t in data["targets"] if t["name"] == "Animatronics")["blocks"]

# =====================================================================
# Fix the relative-movement digit-extraction bug: `previous cam man +
# Random(...)` adds a random offset to the whole string "CAM4" (coerces to 0)
# instead of extracting the trailing digit first via Letter(4, ...), the
# pattern already used correctly inside the rng man/women/women2 custom
# block bodies themselves. Applies to all 6 occurrences (3 in the movement
# loop using Random(-2,2), 3 in the tail move using Random(-1,2)).
# =====================================================================
BUGGY_ADD_BLOCKS = [
    ("Q9c[f?H-q6x-k(d^kzV=", "previous cam man", "8?J{_1xnhtJh]|VrCyW@"),
    ("EAthim|kiA.-@LJ3.`S6", "previous cam woman", "b@(l#~~#Hbql_I/G?OV2"),
    ("v!n?](f{@#sr2BEyypQg", "previous cam woman2", "l(wo=y)GHRzh(d;sJH56"),
    ("E~J|wbj}.dqf-7bqGI.O", "previous cam man", "8?J{_1xnhtJh]|VrCyW@"),
    ("m#;cKRm[v|H]ihulFa++", "previous cam woman", "b@(l#~~#Hbql_I/G?OV2"),
    ("=feOICL:N-]Q6;}9`IuZ", "previous cam woman2", "l(wo=y)GHRzh(d;sJH56"),
]

for add_id, var_name, var_id in BUGGY_ADD_BLOCKS:
    add_block = anim[add_id]
    assert add_block["opcode"] == "operator_add"
    old_num1 = add_block["inputs"]["NUM1"]
    assert old_num1[1] == [12, var_name, var_id], f"{add_id}: unexpected NUM1 {old_num1}"

    letter_id = new_block(
        anim, "operator_letter_of", add_id,
        {"LETTER": [1, [6, "4"]], "STRING": [3, [12, var_name, var_id], [10, ""]]},
        tag="letterfix",
    )
    add_block["inputs"]["NUM1"] = [3, letter_id, [4, ""]]

print("Movement re-invocation digit-extraction bug fixed (6 sites).")

# =====================================================================
# Remove the fully-vestigial orphaned `Control.CreateCloneOf(_myself_)` --
# no `WhenIStartAsClone` hat exists anywhere in this sprite to make use of
# a clone, unlike the movement loop below which is dead-but-needed.
# =====================================================================
VESTIGIAL_CLONE = "G7XwPaic/LmzX[v+4Imb"
assert anim[VESTIGIAL_CLONE]["opcode"] == "control_create_clone_of"
assert anim[VESTIGIAL_CLONE]["topLevel"] is True
assert anim[VESTIGIAL_CLONE]["next"] is None

del anim[anim[VESTIGIAL_CLONE]["inputs"]["CLONE_OPTION"][1]]  # its menu shadow block
del anim[VESTIGIAL_CLONE]

print("Vestigial orphaned CreateCloneOf removed.")

# =====================================================================
# Reconnect the animatronic AI: the initial spawn calls + movement
# Repeat-Until loop (chain A) and the "one last move + reset" tail
# (chain B) are two SEPARATE orphaned top-level scripts with no hat at
# all -- they have never run. Join them under one new WhenGreenFlagClicked
# hat: chain A followed by chain B, matching how the original decompile
# visually presents them as one continuous "Orphaned blocks" section.
# =====================================================================
CHAIN_A_HEAD = "hSF;/i@ENoj*[sf]GF{i"
CHAIN_A_LOOP = "fmgy/ot~2Iw+fvISEq[:"  # the control_repeat_until block itself
CHAIN_B_HEAD = "?Flf2i/B)UvSbD!tB0=,"

assert anim[CHAIN_A_HEAD]["topLevel"] is True
assert anim[CHAIN_A_LOOP]["opcode"] == "control_repeat_until"
assert anim[CHAIN_A_LOOP]["next"] is None
assert anim[CHAIN_B_HEAD]["topLevel"] is True
assert anim[CHAIN_B_HEAD]["parent"] is None

# join chain A's loop tail to chain B's head
anim[CHAIN_A_LOOP]["next"] = CHAIN_B_HEAD
anim[CHAIN_B_HEAD]["parent"] = CHAIN_A_LOOP
anim[CHAIN_B_HEAD]["topLevel"] = False

# new green-flag hat wrapping the whole thing
new_hat = new_block(anim, "event_whenflagclicked", None, {}, next=CHAIN_A_HEAD, tag="animstart")
anim[new_hat]["topLevel"] = True
anim[CHAIN_A_HEAD]["parent"] = new_hat
anim[CHAIN_A_HEAD]["topLevel"] = False

print("Animatronic AI reconnected to green flag.")

bb_check(anim, "Animatronics")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v8) written.")
