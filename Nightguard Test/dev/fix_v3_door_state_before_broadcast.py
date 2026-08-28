import json

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
door = next(t for t in data["targets"] if t["name"] == "Door")["blocks"]

COSTUME2 = "^/@35oTvn`JrA*9wd$15"
BROADCAST = "b[^aJ|fPOb@0XN%Uj}M3"
SET_OPEN = "zNGdoorOpenState001"

assert door[COSTUME2]["next"] == BROADCAST
assert door[BROADCAST]["next"] == SET_OPEN
assert door[SET_OPEN]["next"] is None

# `Office`'s broadcast handler reads `rightdoorstate` the moment it receives the
# "right door" broadcast. The reopen branch was broadcasting *before* setting
# rightdoorstate to "open", so Office could read the stale "closed" value.
# Reorder to match the close branch, which already sets state before
# broadcasting: costume2 -> set rightdoorstate=open -> broadcast "right door".
door[COSTUME2]["next"] = SET_OPEN
door[SET_OPEN]["parent"] = COSTUME2
door[SET_OPEN]["next"] = BROADCAST
door[BROADCAST]["parent"] = SET_OPEN
door[BROADCAST]["next"] = None


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
print("project.json (v3) written.")
