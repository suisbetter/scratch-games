import json

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))

door = next(t for t in data["targets"] if t["name"] == "Door")["blocks"]
office = next(t for t in data["targets"] if t["name"] == "Office")["blocks"]

RIGHTDOORSTATE_VAR = "rightdoorstate"
RIGHTDOORSTATE_ID = "kWwpbLAXTnqMRh?mebX0"
LEFTDOORSTATE_VAR = "leftdoorstate"
LEFTDOORSTATE_ID = "g@nlPnWg(+zgQ9Rs{.5I"

_counter = [0]


def new_id(tag):
    _counter[0] += 1
    return f"zNG{tag}{_counter[0]:03d}"


def add_equals_closed(blocks, parent, var_name, var_id):
    """Create a fresh `<var> == "closed"` operator_equals block, return its id."""
    bid = new_id("eq")
    blocks[bid] = {
        "opcode": "operator_equals",
        "next": None,
        "parent": parent,
        "inputs": {
            "OPERAND1": [3, [12, var_name, var_id], [10, ""]],
            "OPERAND2": [1, [10, "closed"]],
        },
        "fields": {},
        "shadow": False,
        "topLevel": False,
    }
    return bid


def add_switch_costume(blocks, parent, costume_name):
    """Create a fresh looks_switchcostumeto block (+ its shadow looks_costume), return its id."""
    shadow_id = new_id("costumeval")
    block_id = new_id("switchcostume")
    blocks[shadow_id] = {
        "opcode": "looks_costume",
        "next": None,
        "parent": block_id,
        "inputs": {},
        "fields": {"COSTUME": [costume_name, None]},
        "shadow": True,
        "topLevel": False,
    }
    blocks[block_id] = {
        "opcode": "looks_switchcostumeto",
        "next": None,
        "parent": parent,
        "inputs": {"COSTUME": [1, shadow_id]},
        "fields": {},
        "shadow": False,
        "topLevel": False,
    }
    return block_id


def add_wait(blocks, parent, seconds):
    # control_wait's DURATION is an inline literal in this project (type 5 = positive
    # number), not a separate shadow block — matches every existing control_wait here.
    wait_id = new_id("wait")
    blocks[wait_id] = {
        "opcode": "control_wait",
        "next": None,
        "parent": parent,
        "inputs": {"DURATION": [1, [5, str(seconds)]]},
        "fields": {},
        "shadow": False,
        "topLevel": False,
    }
    return wait_id


def chain(blocks, ids):
    """Link a list of already-created block ids into next->...->None, fixing parent along the way."""
    for i, bid in enumerate(ids):
        blocks[bid]["next"] = ids[i + 1] if i + 1 < len(ids) else None
        if i > 0:
            blocks[bid]["parent"] = ids[i - 1]


def build_costume_swap_chain(blocks, parent, first_costume, second_costume, wait_seconds=0.01):
    """Build `switch costume -> wait -> switch costume`, return its head id (chain already linked)."""
    c1 = add_switch_costume(blocks, parent, first_costume)
    w = add_wait(blocks, c1, wait_seconds)
    c2 = add_switch_costume(blocks, w, second_costume)
    chain(blocks, [c1, w, c2])
    return c1


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


# =====================================================================
# PART B1: Door sprite — remove the left door's cross-lock on rightdoorstate
# =====================================================================
WAIT01 = "uA=m*PQ|TgRd4hWk6|?@"
OUTER_IFELSE_D = ".u=}.m+-QoXhLd@o6A76"
STOP_D = "+~cpkLFk$KJY=aJ^wxIy"
COND_D = "/^A9,[2^W~8e*IgM0KBw"
REAL_LOGIC_D = "gAn;TUhtT8+pc2RTSM#v"

assert door[WAIT01]["next"] == OUTER_IFELSE_D
door[WAIT01]["next"] = REAL_LOGIC_D
door[REAL_LOGIC_D]["parent"] = WAIT01
del door[OUTER_IFELSE_D]
del door[STOP_D]
del door[COND_D]
print("Part B1 done (Door cross-lock removed).")

# =====================================================================
# PART B2: Office sprite — remove the mirrored cross-lock on the "left door" handler
# =====================================================================
HAT_LEFTDOOR = "q)l{oaAIG!/m`]/Ehz|x"
OUTER_IFELSE_O = "DBPTKz8A~JWI=$q:*-L6"
STOP_O = "[m%zQZYWNBEz+;dzL:.["
COND_O = "H*$ma%!I}wUg6y,NrTg*"
REAL_LOGIC_O = ".g~@-MR8TN{Hdd,IpB~="

assert office[HAT_LEFTDOOR]["next"] == OUTER_IFELSE_O
office[HAT_LEFTDOOR]["next"] = REAL_LOGIC_O
office[REAL_LOGIC_O]["parent"] = HAT_LEFTDOOR
del office[OUTER_IFELSE_O]
del office[STOP_O]
del office[COND_O]
print("Part B2 done (Office cross-lock removed).")

# =====================================================================
# PART C1: right closes, left already closed -> wire up the existing orphaned block
# =====================================================================
COUNTER_SET_1 = "yHEX%[%y70WpDG^ie9{y"
ORPHAN_IFELSE = "]+;oUR/^:^(*b~}QL9.."

assert office[COUNTER_SET_1]["next"] is None
office[COUNTER_SET_1]["next"] = ORPHAN_IFELSE
office[ORPHAN_IFELSE]["parent"] = COUNTER_SET_1
office[ORPHAN_IFELSE]["topLevel"] = False
print("Part C1 done (orphaned both-closed block wired into right-door close chain).")

# =====================================================================
# PART C2: left closes, right already closed -> both-closed (mirror, new blocks)
# =====================================================================
LEFT_CLOSE_END = "HgcZsqId`jymFuQ2xz3@"  # final costume5 block of Office's left-close chain
assert office[LEFT_CLOSE_END]["next"] is None

new_ifelse_2 = new_id("ifelse")
cond_2 = add_equals_closed(office, new_ifelse_2, RIGHTDOORSTATE_VAR, RIGHTDOORSTATE_ID)
true_head_2 = build_costume_swap_chain(office, new_ifelse_2, "costume12", "costume13")
false_head_2 = build_costume_swap_chain(office, new_ifelse_2, "costume12", "costume5")
office[new_ifelse_2] = {
    "opcode": "control_if_else",
    "next": None,
    "parent": LEFT_CLOSE_END,
    "inputs": {
        "CONDITION": [2, cond_2],
        "SUBSTACK": [2, true_head_2],
        "SUBSTACK2": [2, false_head_2],
    },
    "fields": {},
    "shadow": False,
    "topLevel": False,
}
office[LEFT_CLOSE_END]["next"] = new_ifelse_2
print("Part C2 done (left-closes-second mirror added).")

# =====================================================================
# PART C3: right reopens, left still closed -> land on costume5 not costume1
# =====================================================================
RIGHT_REOPEN_WAIT = "Pbd-rz=3Rzse6P691E0F"
RIGHT_REOPEN_COSTUME1 = "^p,UcfHP=`aUk$moP6`3"  # existing costume1 block, reused as the false branch
RIGHT_REOPEN_COUNTER0 = "yW[mizMa~V]5pzA!!Q#r"

assert office[RIGHT_REOPEN_WAIT]["next"] == RIGHT_REOPEN_COSTUME1
assert office[RIGHT_REOPEN_COSTUME1]["next"] == RIGHT_REOPEN_COUNTER0

new_ifelse_3 = new_id("ifelse")
cond_3 = add_equals_closed(office, new_ifelse_3, LEFTDOORSTATE_VAR, LEFTDOORSTATE_ID)
true_head_3 = add_switch_costume(office, new_ifelse_3, "costume5")

# detach the existing costume1 block and reuse it as the false branch
office[RIGHT_REOPEN_COSTUME1]["parent"] = new_ifelse_3
office[RIGHT_REOPEN_COSTUME1]["next"] = None

office[new_ifelse_3] = {
    "opcode": "control_if_else",
    "next": RIGHT_REOPEN_COUNTER0,
    "parent": RIGHT_REOPEN_WAIT,
    "inputs": {
        "CONDITION": [2, cond_3],
        "SUBSTACK": [2, true_head_3],
        "SUBSTACK2": [2, RIGHT_REOPEN_COSTUME1],
    },
    "fields": {},
    "shadow": False,
    "topLevel": False,
}
office[RIGHT_REOPEN_WAIT]["next"] = new_ifelse_3
office[RIGHT_REOPEN_COUNTER0]["parent"] = new_ifelse_3
print("Part C3 done (right-reopen state-aware landing added).")

# =====================================================================
# PART C4: left reopens, right still closed -> land on costume7 not costume1
# =====================================================================
LEFT_REOPEN_WAIT = "S5LN=_#:YYCf_l5dGtj2"
LEFT_REOPEN_COSTUME1 = "N8I+Q|Rd[moecHE@Bg$#"  # existing costume1 block, reused as the false branch

assert office[LEFT_REOPEN_WAIT]["next"] == LEFT_REOPEN_COSTUME1
assert office[LEFT_REOPEN_COSTUME1]["next"] is None

new_ifelse_4 = new_id("ifelse")
cond_4 = add_equals_closed(office, new_ifelse_4, RIGHTDOORSTATE_VAR, RIGHTDOORSTATE_ID)
true_head_4 = add_switch_costume(office, new_ifelse_4, "costume7")

office[LEFT_REOPEN_COSTUME1]["parent"] = new_ifelse_4
# next already None

office[new_ifelse_4] = {
    "opcode": "control_if_else",
    "next": None,
    "parent": LEFT_REOPEN_WAIT,
    "inputs": {
        "CONDITION": [2, cond_4],
        "SUBSTACK": [2, true_head_4],
        "SUBSTACK2": [2, LEFT_REOPEN_COSTUME1],
    },
    "fields": {},
    "shadow": False,
    "topLevel": False,
}
office[LEFT_REOPEN_WAIT]["next"] = new_ifelse_4
print("Part C4 done (left-reopen state-aware landing added).")

# =====================================================================
# sanity checks + write out
# =====================================================================
check(door, "Door")
check(office, "Office")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v5) written.")
