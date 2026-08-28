import json
import sys
sys.path.insert(0, ".")
from block_builder import (new_block, var_ref, num_lit, str_lit, block_ref_value, block_ref_bool,
                            add_letter_of, add_join, add_length, add_subtract, add_equals, add_ifelse, check)

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
office = next(t for t in data["targets"] if t["name"] == "Office")["blocks"]

# ---------------------------------------------------------------------------
# Real bug: real Scratch's Cast.toNumber is JavaScript's Number(value) with
# NaN -> 0, and Number() requires the *entire* trimmed string to be numeric.
# "50%" is NaN -> 0, not 50. The session-3 fix (`power = Join((power - 1),
# '%')`) operates on `power` directly, including its "%" suffix, so every
# single decrement actually computes `0 - 1 = -1` in the real engine --
# confirmed by fixing dev/interpreter.py's `to_number` (it had a "parse a
# leading numeric run" fallback that isn't how real Scratch behaves, which is
# exactly why this passed before) and re-running: the power loop now never
# reaches "0%" at all under accurate semantics, spinning until the safety cap.
#
# Fix: go back to Letter/Join digit extraction (stripping "%" before doing
# arithmetic) -- which is why the *original* project used it in the first
# place -- but sized correctly. power's real domain is 0-100 (Animatronics'
# green-flag script sets it to '100%', and it only decreases), so the digit
# portion is 1, 2, or 3 characters (power string length 2, 3, or 4 including
# '%'). The old bug was a hardcoded 1-vs-2-digit branch; extend to 1-vs-2-vs-3.
# ---------------------------------------------------------------------------

POWER_VAR_ID = "cvDH$;9j@b_?E@g.5GQ~"

SITES = [
    "ax",  # closed-door branch, 1st decrement
    "dq",  # closed-door branch, 2nd decrement
    "ds",  # open-door branch, single decrement
]


def build_extract(blocks, parent, n_digits):
    """Join of the first n_digits characters of `power`, parented later."""
    letters = [add_letter_of(blocks, parent, i + 1, var_ref("power", POWER_VAR_ID)) for i in range(n_digits)]
    if n_digits == 1:
        return letters[0]
    acc = letters[0]
    for letter_id in letters[1:]:
        acc = add_join(blocks, parent, block_ref_value(acc, ""), block_ref_value(letter_id, ""))
    return acc


def build_decrement_stmt(blocks, parent, next_id, n_digits):
    extract_id = build_extract(blocks, None, n_digits)
    sub_id = add_subtract(blocks, None, block_ref_value(extract_id, "0"), num_lit(1))
    join_id = add_join(blocks, None, block_ref_value(sub_id, "0"), str_lit("%"))
    set_id = new_block(blocks, "data_setvariableto", parent, {"VALUE": block_ref_value(join_id, "0%")},
                        fields={"VARIABLE": ["power", POWER_VAR_ID]}, tag="powerset")
    blocks[set_id]["next"] = next_id
    if next_id:
        blocks[next_id]["parent"] = set_id
    blocks[join_id]["parent"] = set_id
    blocks[sub_id]["parent"] = join_id
    blocks[extract_id]["parent"] = sub_id
    # fix up parents inside the extract chain (build_extract used parent=None throughout)
    reparent_extract_chain(blocks, extract_id)
    return set_id


def reparent_extract_chain(blocks, join_or_letter_id):
    b = blocks[join_or_letter_id]
    if b["opcode"] != "operator_join":
        return
    for key in ("STRING1", "STRING2"):
        child_id = b["inputs"][key][1]
        blocks[child_id]["parent"] = join_or_letter_id
        reparent_extract_chain(blocks, child_id)


def build_power_decrement(blocks, parent, next_id):
    """control_if_else(Length==2){1-digit} Else { control_if_else(Length==3){2-digit} Else {3-digit} }"""
    len1 = add_length(blocks, None, var_ref("power", POWER_VAR_ID))
    eq1 = add_equals(blocks, None, block_ref_value(len1, "0"), str_lit("2"))
    blocks[len1]["parent"] = eq1

    len2 = add_length(blocks, None, var_ref("power", POWER_VAR_ID))
    eq2 = add_equals(blocks, None, block_ref_value(len2, "0"), str_lit("3"))
    blocks[len2]["parent"] = eq2

    branch_1digit = build_decrement_stmt(blocks, None, None, 1)
    branch_2digit = build_decrement_stmt(blocks, None, None, 2)
    branch_3digit = build_decrement_stmt(blocks, None, None, 3)

    inner_ifelse = add_ifelse(blocks, None, eq2, branch_2digit, branch_3digit)
    blocks[eq2]["parent"] = inner_ifelse
    blocks[branch_2digit]["parent"] = inner_ifelse
    blocks[branch_3digit]["parent"] = inner_ifelse

    outer_ifelse = add_ifelse(blocks, parent, eq1, branch_1digit, inner_ifelse)
    blocks[eq1]["parent"] = outer_ifelse
    blocks[branch_1digit]["parent"] = outer_ifelse
    blocks[inner_ifelse]["parent"] = outer_ifelse
    blocks[outer_ifelse]["next"] = next_id
    if next_id:
        blocks[next_id]["parent"] = outer_ifelse
    return outer_ifelse


replaced = 0
for old_id in SITES:
    old_block = office[old_id]
    assert old_block["opcode"] == "data_setvariableto"
    assert old_block["fields"]["VARIABLE"][0] == "power"
    parent_id = old_block["parent"]
    next_id = old_block["next"]
    value_join_id = old_block["inputs"]["VALUE"][1]

    # collect+delete the old VALUE expression subtree (Join/Letter/etc, all self-owned)
    to_remove = set()
    stack = [value_join_id]
    while stack:
        bid = stack.pop()
        if bid in to_remove or bid not in office:
            continue
        to_remove.add(bid)
        b = office[bid]
        for v in b.get("inputs", {}).values():
            if isinstance(v, list) and len(v) > 1 and isinstance(v[1], str) and v[1] in office:
                stack.append(v[1])

    new_head = build_power_decrement(office, parent_id, next_id)

    # rewire whatever pointed at old_id to point at new_head instead
    if office[parent_id].get("next") == old_id:
        office[parent_id]["next"] = new_head
    else:
        for key in ("SUBSTACK", "SUBSTACK2"):
            ins = office[parent_id].get("inputs", {})
            if key in ins and ins[key][1] == old_id:
                ins[key][1] = new_head

    for bid in to_remove:
        del office[bid]
    del office[old_id]
    replaced += 1

check(office, "Office (power real-coercion fix)")
print(f"Sanity check passed. Replaced {replaced} decrement sites with 3-way digit extraction.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v17) written.")
