import json
import sys
sys.path.insert(0, ".")
from block_builder import new_block, var_ref, num_lit, str_lit, block_ref_value, block_ref_bool, check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
an = next(t for t in data["targets"] if t["name"] == "Animatronics")["blocks"]

# ---------------------------------------------------------------------------
# Found while writing a fairness regression test for the previous session's
# spawn-fairness fix (not something the user reported directly, but a real
# bug the test caught): each `rng *` procedure's "clear old slot" step
# unconditionally overwrites `camlist[previous position]`, with no check
# that the slot still actually holds *this* animatronic's own marker. If two
# animatronics' positions collide within the same 4-second tick -- animatronic
# B's fresh new position happens to equal animatronic A's old position, and B
# is processed (man, then women1, then women2, in that fixed order) *after*
# A already wrote its own old-slot clear -- no problem; but if B runs *before*
# A in the same tick and B's *old* slot is the one A just wrote *into*, B's
# clear step wipes out A's brand-new mark. Reproduced directly: with man
# starting at CAM2 and women1 starting at CAM8, man moves to CAM8 (writing
# "man(CAM8)"), then women1's own clear step (still keyed off its *old*
# position CAM8) overwrites that same slot back to a bare "CAM8" -- man's
# mark is gone even though man is still really there.
#
# Fix: guard each clear step so it only fires if the slot still contains
# *this animatronic's own* tag -- using the same `Contains` pattern Office's
# jumpscare detection already uses elsewhere in this project. If another
# animatronic has since legitimately claimed that slot, skip clearing it.
# ---------------------------------------------------------------------------

CAMLIST_ID = "aH(4E3xESYnTf3`u|U$Q"

SITES = [
    # (head_of_procedure, old_clear_step_id, previous_cam_var_name, previous_cam_var_id, own_tag)
    ("b[", "X", "previous cam man", "8?J{_1xnhtJh]|VrCyW@", "man"),
    ("b~", "Z", "previous cam woman", "b@(l#~~#Hbql_I/G?OV2", "women1"),
    ("ch", "#", "previous cam woman2", "l(wo=y)GHRzh(d;sJH56", "women2"),
]

for head_id, clear_id, var_name, var_id, tag in SITES:
    clear_block = an[clear_id]
    assert clear_block["opcode"] == "data_replaceitemoflist"
    assert an[head_id]["next"] == clear_id
    after_clear = clear_block["next"]

    letter_id = new_block(an, "operator_letter_of", None,
                           {"LETTER": num_lit(4), "STRING": var_ref(var_name, var_id)}, tag="guardletter")
    item_id = new_block(an, "data_itemoflist", None, {"INDEX": block_ref_value(letter_id, "1")},
                         fields={"LIST": ["camlist", CAMLIST_ID]}, tag="guarditem")
    contains_id = new_block(an, "operator_contains", None,
                             {"STRING1": block_ref_value(item_id, ""), "STRING2": str_lit(tag)}, tag="guardcontains")
    an[letter_id]["parent"] = item_id
    an[item_id]["parent"] = contains_id

    guard_if = new_block(an, "control_if", head_id,
                          {"CONDITION": block_ref_bool(contains_id), "SUBSTACK": [2, clear_id]}, tag="guardif")
    an[contains_id]["parent"] = guard_if

    an[head_id]["next"] = guard_if
    an[guard_if]["next"] = after_clear
    if after_clear:
        an[after_clear]["parent"] = guard_if
    an[clear_id]["parent"] = guard_if
    an[clear_id]["next"] = None

check(an, "Animatronics (camlist clear-slot guard)")
print("Sanity check passed. Guarded 3 clear-old-slot steps against cross-animatronic overwrite.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v18) written.")
