import json
import sys
sys.path.insert(0, ".")
from block_builder import new_block, var_ref, num_lit, str_lit, block_ref_value, check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
office = next(t for t in data["targets"] if t["name"] == "Office")["blocks"]

# ---------------------------------------------------------------------------
# Bug: `Animatronics`' green-flag hat sets `power = '100%'` at game start (the
# real runtime starting value -- Stage's serialized '95%' default is just a
# stale saved-editor-state snapshot, consistent with every other stateful
# variable in this project being explicitly reset by its owning sprite's own
# green-flag script). But the power-drain loop's digit extraction assumes
# power is *never* more than 2 characters long: `If (Length(power) == '2')
# { <1-digit> } Else { <take exactly the first 2 characters> }`. At
# power == '100%' (4 chars), that Else branch reads only "10" (dropping the
# third digit) and decrements to "9%" -- an instant ~91-point collapse on the
# very first tick. Confirmed via interpreter.py starting from '100%'.
#
# Fix: Scratch's arithmetic operators already coerce a string like "100%" to
# its leading numeric value (confirmed against this project's own
# interpreter.py::to_number, which models exactly that). Replace all three
# duplicated length-branching extraction blocks with one direct expression --
# `power = Join((power - 1), '%')` -- correct for any digit count.
# ---------------------------------------------------------------------------

POWER_VAR_ID = "cvDH$;9j@b_?E@g.5GQ~"

REPLACE_SITES = [
    # (ifelse_block_id, parent_id, next_id, "how the parent references it")
    ("zNGv7ifelse0016", "zNGv7ifelse0047", "zNGv7if0033", "SUBSTACK"),
    ("zNGv7ifelse0032", "zNGv7wait0019", None, "next"),
    ("zNGv7ifelse0046", "zNGv7ifelse0047", None, "SUBSTACK2"),
]


def referenced_block_ids(blocks, bid):
    b = blocks[bid]
    out = []
    for v in b.get("inputs", {}).values():
        if not isinstance(v, list):
            continue
        for item in v[1:]:
            if isinstance(item, str) and item in blocks:
                out.append(item)
            elif isinstance(item, list) and len(item) > 1 and isinstance(item[1], str) and item[1] in blocks:
                out.append(item[1])
    return out


def collect_own_subtree(blocks, start):
    """All block ids `start` itself owns: its own inputs (conditions,
    substacks -- each substack's *entire* next-chain, since that chain
    belongs only to this block) -- but NOT anything reachable via `start`'s
    own `next` pointer, which is a sibling statement, not part of `start`."""
    seen = {start}
    stack = referenced_block_ids(blocks, start)
    while stack:
        bid = stack.pop()
        if bid in seen or bid not in blocks:
            continue
        seen.add(bid)
        b = blocks[bid]
        if b.get("next"):
            stack.append(b["next"])
        stack.extend(referenced_block_ids(blocks, bid))
    return seen


def make_decrement_block(parent, next_id):
    sub_id = new_block(office, "operator_subtract", None,
                        {"NUM1": var_ref("power", POWER_VAR_ID), "NUM2": num_lit(1)}, tag="powersub")
    join_id = new_block(office, "operator_join", None,
                         {"STRING1": block_ref_value(sub_id), "STRING2": str_lit("%")}, tag="powerjoin")
    set_id = new_block(office, "data_setvariableto", parent,
                        {"VALUE": block_ref_value(join_id)},
                        fields={"VARIABLE": ["power", POWER_VAR_ID]}, tag="powerset")
    office[sub_id]["parent"] = join_id
    office[join_id]["parent"] = set_id
    office[set_id]["next"] = next_id
    if next_id:
        office[next_id]["parent"] = set_id
    return set_id


removed_total = 0
for old_id, parent_id, next_id, ref_kind in REPLACE_SITES:
    old_block = office[old_id]
    assert old_block["opcode"] == "control_if_else"
    to_remove = collect_own_subtree(office, old_id)

    new_id = make_decrement_block(parent_id, next_id)

    if ref_kind == "next":
        assert office[parent_id]["next"] == old_id
        office[parent_id]["next"] = new_id
    else:
        office[parent_id]["inputs"][ref_kind] = [2, new_id]

    for bid in to_remove:
        del office[bid]
    removed_total += len(to_remove)

check(office, "Office (power digit fix)")
print(f"Sanity check passed. Removed {removed_total} old blocks, added 9 new ones.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v14) written.")
