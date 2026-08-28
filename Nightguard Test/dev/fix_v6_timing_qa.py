import json

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))

door = next(t for t in data["targets"] if t["name"] == "Door")["blocks"]
office = next(t for t in data["targets"] if t["name"] == "Office")["blocks"]

_counter = [0]


def new_id(tag):
    _counter[0] += 1
    return f"zNGqa{tag}{_counter[0]:03d}"


def add_switch_costume(blocks, parent, costume_name):
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
# FIX 1: remove the left door's arbitrary 0.1s upfront click delay
# (confirmed via exploration: no sound/animation dependency on it)
# =====================================================================
LEFT_CLICK_HAT = "bLmg7{PQ|g!kc$VSIpwg"
LEFT_WAIT_0_1 = "uA=m*PQ|TgRd4hWk6|?@"
REAL_LOGIC_D = "gAn;TUhtT8+pc2RTSM#v"

assert door[LEFT_CLICK_HAT]["next"] == LEFT_WAIT_0_1
assert door[LEFT_WAIT_0_1]["next"] == REAL_LOGIC_D
door[LEFT_CLICK_HAT]["next"] = REAL_LOGIC_D
door[REAL_LOGIC_D]["parent"] = LEFT_CLICK_HAT
del door[LEFT_WAIT_0_1]
print("Fix 1 done (left door 0.1s upfront delay removed).")

# =====================================================================
# FIX 2: standardize right-door transition waits from 0.001 -> 0.01
# =====================================================================
RIGHT_CLOSE_WAIT = "{g]V%c^d(E-a_grfAD)m"
RIGHT_REOPEN_WAIT = "Pbd-rz=3Rzse6P691E0F"

for bid in (RIGHT_CLOSE_WAIT, RIGHT_REOPEN_WAIT):
    assert office[bid]["opcode"] == "control_wait"
    assert office[bid]["inputs"]["DURATION"] == [1, [5, "0.001"]]
    office[bid]["inputs"]["DURATION"] = [1, [5, "0.01"]]
print("Fix 2 done (right-door transition waits standardized to 0.01).")

# =====================================================================
# FIX 3: add the missing transition frame to the reopen-state-aware
# branches added earlier this session (instant snap -> costume12 lead-in)
# =====================================================================

# --- right-reopen-while-left-still-closed branch: lands on costume5 ---
# find it: the if/else inserted between the right-reopen wait and the counter reset
right_ifelse_id = office[RIGHT_REOPEN_WAIT]["next"]
right_ifelse = office[right_ifelse_id]
assert right_ifelse["opcode"] == "control_if_else"
old_true_head_r = right_ifelse["inputs"]["SUBSTACK"][1]
assert office[old_true_head_r]["opcode"] == "looks_switchcostumeto"
old_true_costume_r = office[office[old_true_head_r]["inputs"]["COSTUME"][1]]["fields"]["COSTUME"][0]
assert old_true_costume_r == "costume5"
assert office[old_true_head_r]["next"] is None

new_true_head_r = add_switch_costume(office, right_ifelse_id, "costume12")
w_r = add_wait(office, new_true_head_r, 0.01)
office[new_true_head_r]["next"] = w_r
office[w_r]["next"] = old_true_head_r
office[old_true_head_r]["parent"] = w_r
right_ifelse["inputs"]["SUBSTACK"] = [2, new_true_head_r]

# --- left-reopen-while-right-still-closed branch: lands on costume7 ---
LEFT_REOPEN_WAIT = "S5LN=_#:YYCf_l5dGtj2"
left_ifelse_id = office[LEFT_REOPEN_WAIT]["next"]
left_ifelse = office[left_ifelse_id]
assert left_ifelse["opcode"] == "control_if_else"
old_true_head_l = left_ifelse["inputs"]["SUBSTACK"][1]
assert office[old_true_head_l]["opcode"] == "looks_switchcostumeto"
old_true_costume_l = office[office[old_true_head_l]["inputs"]["COSTUME"][1]]["fields"]["COSTUME"][0]
assert old_true_costume_l == "costume7"
assert office[old_true_head_l]["next"] is None

new_true_head_l = add_switch_costume(office, left_ifelse_id, "costume12")
w_l = add_wait(office, new_true_head_l, 0.01)
office[new_true_head_l]["next"] = w_l
office[w_l]["next"] = old_true_head_l
office[old_true_head_l]["parent"] = w_l
left_ifelse["inputs"]["SUBSTACK"] = [2, new_true_head_l]

print("Fix 3 done (transition frames added to reopen-state-aware branches).")

# =====================================================================
# sanity + write out
# =====================================================================
check(door, "Door")
check(office, "Office")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v6) written.")
