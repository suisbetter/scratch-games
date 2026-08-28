import json

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
door = next(t for t in data["targets"] if t["name"] == "Door")["blocks"]

IF_ELSE = "DS-(O!4uIDa^*g|alQ4*"
assert door[IF_ELSE]["opcode"] == "control_if_else"
assert door[IF_ELSE]["next"] is None

WAIT_RELEASE = "zNGwaitRelease001"
NOT_BLOCK = "zNGnotMouseDown001"
MOUSEDOWN_BLOCK = "zNGmousedown002"

# The right-door clone detects clicks with `Wait Until (touching mouse AND mouse
# down)` inside a Forever loop, with no wait for mouse-release afterward. Since a
# real click spans multiple frames, that condition can stay true across several
# loop iterations, firing the toggle 2-3 times for one physical click. Add the
# missing debounce.
door[MOUSEDOWN_BLOCK] = {
    "opcode": "sensing_mousedown",
    "next": None,
    "parent": NOT_BLOCK,
    "inputs": {},
    "fields": {},
    "shadow": False,
    "topLevel": False,
}
door[NOT_BLOCK] = {
    "opcode": "operator_not",
    "next": None,
    "parent": WAIT_RELEASE,
    "inputs": {"OPERAND": [2, MOUSEDOWN_BLOCK]},
    "fields": {},
    "shadow": False,
    "topLevel": False,
}
door[WAIT_RELEASE] = {
    "opcode": "control_wait_until",
    "next": None,
    "parent": IF_ELSE,
    "inputs": {"CONDITION": [2, NOT_BLOCK]},
    "fields": {},
    "shadow": False,
    "topLevel": False,
}
door[IF_ELSE]["next"] = WAIT_RELEASE


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


check(door, "Door")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v4) written.")
