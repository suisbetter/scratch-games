import json
import sys
sys.path.insert(0, ".")
from block_builder import check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
office = next(t for t in data["targets"] if t["name"] == "Office")["blocks"]

# ---------------------------------------------------------------------------
# Reported symptom: door transitions sometimes skip their intermediate frame,
# and clicks feel inconsistently laggy -- on both sides, not one more than
# the other (confirmed by re-checking: every left/right transition branch is
# already structurally symmetric, 2 waits for closing and 1-2 for reopening
# on both sides).
#
# Every door-transition wait in this project is `0.01s` -- at or below a
# single real rendered frame (30fps ~= 33ms, 60fps ~= 16.7ms). Whether that
# transition costume and the input-polling tick actually land inside a
# 10ms window is going to vary by machine/framerate/load, which is exactly
# "inconsistent" rather than a deterministic bug -- and matches both
# reported symptoms. Bump to 0.05s: ~3x margin over even a 60fps frame,
# while still reading as instant to a human.
# ---------------------------------------------------------------------------

RIGHT_DOOR_HAT = "@d:QNjylxkr!=i8wi.IU"
LEFT_DOOR_HAT = "q)l{oaAIG!/m`]/Ehz|x"


def refs(blocks, bid):
    b = blocks[bid]
    out = []
    for v in b.get("inputs", {}).values():
        if not isinstance(v, list):
            continue
        for item in v[1:]:
            if isinstance(item, str) and item in blocks:
                out.append(item)
    return out


def collect_waits(blocks, start):
    seen = set()
    stack = [start]
    waits = []
    while stack:
        bid = stack.pop()
        if bid in seen or bid not in blocks:
            continue
        seen.add(bid)
        b = blocks[bid]
        if b["opcode"] == "control_wait":
            waits.append(bid)
        if b.get("next"):
            stack.append(b["next"])
        stack.extend(refs(blocks, bid))
    return waits


NEW_DURATION = "0.05"
changed = 0
for hat in (RIGHT_DOOR_HAT, LEFT_DOOR_HAT):
    for wait_id in collect_waits(office, office[hat]["next"]):
        dur_input = office[wait_id]["inputs"]["DURATION"]
        assert dur_input[1][1] == "0.01", f"{wait_id} unexpected duration {dur_input}"
        dur_input[1][1] = NEW_DURATION
        changed += 1

assert changed == 10, f"expected 10 door waits, changed {changed}"

check(office, "Office (door wait duration)")
print(f"Sanity check passed. Bumped {changed} door-transition waits to {NEW_DURATION}s.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v15) written.")
