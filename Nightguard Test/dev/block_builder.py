"""Reusable Scratch block-construction helpers, built from patterns verified
against this project's actual project.json encoding."""

_counter = [0]


def new_id(tag):
    _counter[0] += 1
    return f"zNGv7{tag}{_counter[0]:04d}"


def var_ref(name, vid, shadow=""):
    return [3, [12, name, vid], [10, shadow]]


def str_lit(s):
    return [1, [10, s]]


def num_lit(n):
    return [1, [6, str(n)]]


def pos_num_lit(n):
    return [1, [5, str(n)]]


def block_ref_value(bid, shadow=""):
    return [3, bid, [10, shadow]]


def block_ref_bool(bid):
    return [2, bid]


def new_block(blocks, opcode, parent, inputs, fields=None, next=None, tag=None):
    bid = new_id(tag or opcode.split("_")[-1][:10])
    blocks[bid] = {
        "opcode": opcode,
        "next": next,
        "parent": parent,
        "inputs": inputs,
        "fields": fields or {},
        "shadow": False,
        "topLevel": False,
    }
    return bid


def reparent(blocks, child_id, new_parent_id):
    blocks[child_id]["parent"] = new_parent_id


def chain(blocks, ids):
    """Link already-existing block ids into next -> ... -> None, fixing parent."""
    for i, bid in enumerate(ids):
        blocks[bid]["next"] = ids[i + 1] if i + 1 < len(ids) else None
        if i > 0:
            blocks[bid]["parent"] = ids[i - 1]


def add_letter_of(blocks, parent, letter, string_input):
    bid = new_block(blocks, "operator_letter_of", parent, {"LETTER": num_lit(letter), "STRING": string_input}, tag="letterof")
    return bid


def add_join(blocks, parent, s1, s2):
    return new_block(blocks, "operator_join", parent, {"STRING1": s1, "STRING2": s2}, tag="join")


def add_length(blocks, parent, string_input):
    return new_block(blocks, "operator_length", parent, {"STRING": string_input}, tag="length")


def add_subtract(blocks, parent, n1, n2):
    return new_block(blocks, "operator_subtract", parent, {"NUM1": n1, "NUM2": n2}, tag="sub")


def add_add(blocks, parent, n1, n2):
    return new_block(blocks, "operator_add", parent, {"NUM1": n1, "NUM2": n2}, tag="add")


def add_equals(blocks, parent, o1, o2):
    return new_block(blocks, "operator_equals", parent, {"OPERAND1": o1, "OPERAND2": o2}, tag="eq")


def add_not_equals_via_not(blocks, parent, eq_id):
    return new_block(blocks, "operator_not", parent, {"OPERAND": block_ref_bool(eq_id)}, tag="not")


def add_or(blocks, parent, o1, o2):
    return new_block(blocks, "operator_or", parent, {"OPERAND1": o1, "OPERAND2": o2}, tag="or")


def add_and(blocks, parent, o1, o2):
    return new_block(blocks, "operator_and", parent, {"OPERAND1": o1, "OPERAND2": o2}, tag="and")


def add_setvar(blocks, parent, varname, varid, value_block_id):
    return new_block(blocks, "data_setvariableto", parent, {"VALUE": block_ref_value(value_block_id)},
                      fields={"VARIABLE": [varname, varid]}, tag="set")


def add_setvar_literal(blocks, parent, varname, varid, literal_str):
    return new_block(blocks, "data_setvariableto", parent, {"VALUE": str_lit(literal_str)},
                      fields={"VARIABLE": [varname, varid]}, tag="set")


def add_if(blocks, parent, cond_id, substack_id):
    return new_block(blocks, "control_if", parent, {"CONDITION": block_ref_bool(cond_id), "SUBSTACK": [2, substack_id]}, tag="if")


def add_ifelse(blocks, parent, cond_id, sub1_id, sub2_id):
    return new_block(blocks, "control_if_else", parent,
                      {"CONDITION": block_ref_bool(cond_id), "SUBSTACK": [2, sub1_id], "SUBSTACK2": [2, sub2_id]}, tag="ifelse")


def add_repeat_until(blocks, parent, cond_id, substack_id):
    return new_block(blocks, "control_repeat_until", parent, {"CONDITION": block_ref_bool(cond_id), "SUBSTACK": [2, substack_id]}, tag="repuntil")


def add_wait(blocks, parent, seconds):
    return new_block(blocks, "control_wait", parent, {"DURATION": pos_num_lit(seconds)}, tag="wait")


def add_switch_costume(blocks, parent, costume_name):
    shadow_id = new_block(blocks, "looks_costume", None, {}, fields={"COSTUME": [costume_name, None]}, tag="costumeval")
    blocks[shadow_id]["shadow"] = True
    block_id = new_block(blocks, "looks_switchcostumeto", parent, {"COSTUME": [1, shadow_id]}, tag="switchcostume")
    blocks[shadow_id]["parent"] = block_id
    return block_id


def check(blocks, label):
    ids = set(blocks.keys())
    for bid, b in blocks.items():
        if not isinstance(b, dict):
            continue
        if b.get("next") and b["next"] not in ids:
            raise AssertionError(f"{label}: {bid} next -> missing {b['next']}")
        if b.get("parent") and b["parent"] not in ids:
            raise AssertionError(f"{label}: {bid} parent -> missing {b['parent']}")
        for k, v in (b.get("inputs") or {}).items():
            if isinstance(v, list) and len(v) >= 2 and isinstance(v[1], str):
                if v[1] not in ids:
                    raise AssertionError(f"{label}: {bid} input {k} -> missing {v[1]}")
