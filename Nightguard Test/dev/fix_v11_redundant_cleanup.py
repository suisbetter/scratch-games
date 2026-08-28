import json

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
door = next(t for t in data["targets"] if t["name"] == "Door")["blocks"]
office = next(t for t in data["targets"] if t["name"] == "Office")["blocks"]

# Door.txt: two identical `WhenBroadcastReceived(show) { Looks.Show(); }` hats.
# Remove the duplicate.
DUP_SHOW_HAT = "[|82ojaH$+57-tT*!(0o"
DUP_SHOW_BODY = "/_#p7coA|K7r{*%G4uf?"
assert door[DUP_SHOW_HAT]["opcode"] == "event_whenbroadcastreceived"
assert door[DUP_SHOW_HAT]["fields"]["BROADCAST_OPTION"][0] == "show"
assert door[DUP_SHOW_HAT]["next"] == DUP_SHOW_BODY
del door[DUP_SHOW_BODY]
del door[DUP_SHOW_HAT]
print("Door.txt duplicate 'show' handler removed.")

# Office.txt: a completely empty `WhenBroadcastReceived(left door) { }` hat
# alongside the real handler. Confirmed harmless (does nothing) -- remove it.
EMPTY_LEFTDOOR_HAT = "GGB%/ktM4h.6-B%#J(;="
assert office[EMPTY_LEFTDOOR_HAT]["opcode"] == "event_whenbroadcastreceived"
assert office[EMPTY_LEFTDOOR_HAT]["fields"]["BROADCAST_OPTION"][0] == "left door"
assert office[EMPTY_LEFTDOOR_HAT]["next"] is None
del office[EMPTY_LEFTDOOR_HAT]
print("Office.txt empty 'left door' handler removed.")


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
check(office, "Office")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v11) written.")
