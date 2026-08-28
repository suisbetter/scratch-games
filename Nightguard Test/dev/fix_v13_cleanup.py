import json
import sys
sys.path.insert(0, ".")
from block_builder import check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))


def target(name):
    return next(t for t in data["targets"] if t["name"] == name)


# ---------------------------------------------------------------------------
# Cleanup 1: `index` (Door.txt) was dead -- set once, incremented only by a
# topLevel `data_changevariableby` block with no hat above it (never runs),
# and read nowhere in the project. Remove it entirely rather than leaving it
# parked: the orphaned increment block, the initialization statement in
# Door's green-flag script, and the global variable declaration itself.
# ---------------------------------------------------------------------------
door = target("Door")["blocks"]

ORPHAN_INCREMENT = "Xf(piBQ^9,P.v+buVmEW"
INDEX_INIT = "=/DVe]8bZi#[@OBJR*`6"
SWITCH_COSTUME = "a:JK+|_H~P:D~PNG.t+b"

assert door[ORPHAN_INCREMENT]["opcode"] == "data_changevariableby"
assert door[ORPHAN_INCREMENT]["topLevel"] is True
assert door[INDEX_INIT]["opcode"] == "data_setvariableto"
assert door[INDEX_INIT]["fields"]["VARIABLE"][0] == "index"
assert door[SWITCH_COSTUME]["next"] == INDEX_INIT

next_after_init = door[INDEX_INIT]["next"]
door[SWITCH_COSTUME]["next"] = next_after_init
door[next_after_init]["parent"] = SWITCH_COSTUME
del door[INDEX_INIT]
del door[ORPHAN_INCREMENT]

INDEX_VAR_ID = "OtKUFl5Iv)zAc1fYx+R|"
stage_vars = target("Stage")["variables"]
assert stage_vars[INDEX_VAR_ID][0] == "index"
del stage_vars[INDEX_VAR_ID]

check(door, "Door (index cleanup)")
print("Cleanup 1 (index) done.")

# ---------------------------------------------------------------------------
# Cleanup 2: CamMenu.txt duplicates the same toggle logic between its
# `when this sprite clicked` and `when key [space] pressed` handlers (each
# does: wait 0.1, then the same two `if menucounter == ...` branches). Factor
# the shared body into a no-arg custom block `toggle cam menu` and call it
# from both hats.
# ---------------------------------------------------------------------------
cammenu_target = target("CamMenu")
cm = cammenu_target["blocks"]

CLICK_HAT = "[}GXuHtQ~4Fh1ED%DX`x"
KEY_HAT = "Jv.2YER5`c{2!#Y*{J81"
CLICK_BODY_HEAD = "iwDh`[wrCrX*)4BeDg)o"   # control_wait(0.1) -> if -> if  (kept as the shared body)
KEY_BODY_HEAD = "hZH@f)#P7UG,,W$OCf|w"     # identical duplicate (deleted)

assert cm[CLICK_HAT]["opcode"] == "event_whenthisspriteclicked"
assert cm[KEY_HAT]["opcode"] == "event_whenkeypressed"
assert cm[CLICK_HAT]["next"] == CLICK_BODY_HEAD
assert cm[KEY_HAT]["next"] == KEY_BODY_HEAD


def collect_subtree(blocks, start):
    """All block ids reachable from `start` via next/substacks/inputs (a
    single statement chain and everything it owns), for safe deletion of an
    isolated duplicate chain."""
    seen = set()
    stack = [start]
    while stack:
        bid = stack.pop()
        if bid in seen or bid not in blocks:
            continue
        seen.add(bid)
        b = blocks[bid]
        if b.get("next"):
            stack.append(b["next"])
        for v in b.get("inputs", {}).values():
            if not isinstance(v, list):
                continue
            for item in v[1:]:
                if isinstance(item, str) and item in blocks:
                    stack.append(item)
                elif isinstance(item, list) and len(item) > 1 and isinstance(item[1], str) and item[1] in blocks:
                    stack.append(item[1])
    return seen


PROCCODE = "toggle cam menu"
DEF_ID = "zNGprocdef0001"
PROTO_ID = "zNGprocproto0001"
CALL_CLICK_ID = "zNGproccall0001"
CALL_KEY_ID = "zNGproccall0002"

# Move the click hat's existing chain under the new procedure definition.
cm[DEF_ID] = {
    "opcode": "procedures_definition",
    "next": CLICK_BODY_HEAD,
    "parent": None,
    "inputs": {"custom_block": [2, PROTO_ID]},
    "fields": {},
    "shadow": False,
    "topLevel": True,
    "x": 1400,
    "y": 400,
}
cm[PROTO_ID] = {
    "opcode": "procedures_prototype",
    "next": None,
    "parent": DEF_ID,
    "inputs": {},
    "fields": {},
    "shadow": False,
    "topLevel": False,
    "mutation": {
        "tagName": "mutation", "children": [], "proccode": PROCCODE,
        "argumentids": "[]", "argumentnames": "[]", "argumentdefaults": "[]", "warp": "false",
    },
}
cm[CLICK_BODY_HEAD]["parent"] = DEF_ID

call_mutation = {"tagName": "mutation", "children": [], "proccode": PROCCODE, "argumentids": "[]", "warp": "false"}
cm[CALL_CLICK_ID] = {
    "opcode": "procedures_call", "next": None, "parent": CLICK_HAT,
    "inputs": {}, "fields": {}, "shadow": False, "topLevel": False,
    "mutation": dict(call_mutation),
}
cm[CLICK_HAT]["next"] = CALL_CLICK_ID

cm[CALL_KEY_ID] = {
    "opcode": "procedures_call", "next": None, "parent": KEY_HAT,
    "inputs": {}, "fields": {}, "shadow": False, "topLevel": False,
    "mutation": dict(call_mutation),
}
key_body_ids = collect_subtree(cm, KEY_BODY_HEAD)
cm[KEY_HAT]["next"] = CALL_KEY_ID
for bid in key_body_ids:
    del cm[bid]

check(cm, "CamMenu (dedup)")
print(f"Cleanup 2 (CamMenu dedup) done, removed {len(key_body_ids)} duplicate blocks.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v13) written.")
