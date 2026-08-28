import json
import sys
sys.path.insert(0, ".")
from block_builder import new_block, block_ref_bool, var_ref, str_lit, check as bb_check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
office = next(t for t in data["targets"] if t["name"] == "Office")["blocks"]

RIGHTDOOR = ("rightdoorstate", "kWwpbLAXTnqMRh?mebX0")
LEFTDOOR = ("leftdoorstate", "g@nlPnWg(+zgQ9Rs{.5I")

HAT = "mQx}93w6i5M9@.Wk_F1{"
OLD_OUTER_IF = "-G^romV2E#N.`aO%;]DU"

CAM1_ORCHAIN = "kffFNdku}XGdskuUh/Qm"
CAM2_ORCHAIN = "[!*`A.,u]w#CK(]w]9#G"
COSTUME8_CHAIN_HEAD = "fKcu`1-#_mTNSR:KEv]!"
COSTUME9_CHAIN_HEAD = "d(QDg]@I77TInOJoI#RJ"
COSTUME8_STOP = "$(/3(/^yIZZm5]VZh,E1"
COSTUME9_STOP = "BUe,u-_hfVp-x:k[?e|Y"

assert office[HAT]["next"] == OLD_OUTER_IF
assert office[COSTUME8_CHAIN_HEAD]["next"] == "KXc)v3C~}1mc+Hjqramu"
assert office["KXc)v3C~}1mc+Hjqramu"]["next"] == COSTUME8_STOP
assert office[COSTUME9_CHAIN_HEAD]["next"] == "|.3}Js4FG?2;|aZmnFR?"
assert office["|.3}Js4FG?2;|aZmnFR?"]["next"] == COSTUME9_STOP

# The gate used to be: if EITHER door is closed, skip checking BOTH cameras
# entirely. That means closing the right door also blinds camera 1's
# (left-side) detection, and vice versa. Rebuild as two independent checks,
# each gated only by its own door, keeping the original "camera 1 wins if
# both are active at once" tie-break by nesting camera 2's check in the
# else branch.
not_left_eq = new_block(office, "operator_equals", None, {"OPERAND1": var_ref(*LEFTDOOR), "OPERAND2": str_lit("closed")}, tag="lefteq")
not_left = new_block(office, "operator_not", None, {"OPERAND": block_ref_bool(not_left_eq)}, tag="notleft")
office[not_left_eq]["parent"] = not_left

not_right_eq = new_block(office, "operator_equals", None, {"OPERAND1": var_ref(*RIGHTDOOR), "OPERAND2": str_lit("closed")}, tag="righteq")
not_right = new_block(office, "operator_not", None, {"OPERAND": block_ref_bool(not_right_eq)}, tag="notright")
office[not_right_eq]["parent"] = not_right

cam1_and = new_block(office, "operator_and", None, {"OPERAND1": block_ref_bool(not_left), "OPERAND2": block_ref_bool(CAM1_ORCHAIN)}, tag="cam1and")
office[not_left]["parent"] = cam1_and
office[CAM1_ORCHAIN]["parent"] = cam1_and

cam2_and = new_block(office, "operator_and", None, {"OPERAND1": block_ref_bool(not_right), "OPERAND2": block_ref_bool(CAM2_ORCHAIN)}, tag="cam2and")
office[not_right]["parent"] = cam2_and
office[CAM2_ORCHAIN]["parent"] = cam2_and

# detach the costume8/9 chains from their old trailing Stop blocks
office[COSTUME8_CHAIN_HEAD]  # unchanged head
office["KXc)v3C~}1mc+Hjqramu"]["next"] = None
office["|.3}Js4FG?2;|aZmnFR?"]["next"] = None
del office[COSTUME8_STOP]
del office[COSTUME9_STOP]

cam2_if = new_block(office, "control_if", None, {"CONDITION": block_ref_bool(cam2_and), "SUBSTACK": [2, COSTUME9_CHAIN_HEAD]}, tag="cam2if")
office[cam2_and]["parent"] = cam2_if
office[COSTUME9_CHAIN_HEAD]["parent"] = cam2_if

cam1_ifelse = new_block(office, "control_if_else", None,
                         {"CONDITION": block_ref_bool(cam1_and), "SUBSTACK": [2, COSTUME8_CHAIN_HEAD], "SUBSTACK2": [2, cam2_if]},
                         tag="cam1ifelse")
office[cam1_and]["parent"] = cam1_ifelse
office[COSTUME8_CHAIN_HEAD]["parent"] = cam1_ifelse
office[cam2_if]["parent"] = cam1_ifelse

office[HAT]["next"] = cam1_ifelse


def collect_subtree(blocks, root, exclude):
    ids = set()
    stack = [root]
    while stack:
        bid = stack.pop()
        if bid in ids or bid in exclude or bid not in blocks:
            continue
        ids.add(bid)
        b = blocks[bid]
        if b.get("next"):
            stack.append(b["next"])
        for v in (b.get("inputs") or {}).values():
            if isinstance(v, list) and len(v) >= 2 and isinstance(v[1], str):
                stack.append(v[1])
    return ids


# The old subtree still holds stale *input* references to the pieces we just
# reused (their "parent" pointers were updated above, but the old wrapper
# blocks' own "inputs" dicts were never touched) -- compute what's reachable
# from the reused pieces first so the deletion pass below excludes them.
reused = set()
for root in (CAM1_ORCHAIN, CAM2_ORCHAIN, COSTUME8_CHAIN_HEAD, COSTUME9_CHAIN_HEAD):
    reused |= collect_subtree(office, root, exclude=set())

for bid in collect_subtree(office, OLD_OUTER_IF, exclude=reused):
    del office[bid]

bb_check(office, "Office")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v9) written.")
