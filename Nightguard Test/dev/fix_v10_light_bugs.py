import json
import sys
sys.path.insert(0, ".")
from block_builder import new_block, block_ref_bool, check as bb_check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
light = next(t for t in data["targets"] if t["name"] == "Light")["blocks"]

HAT = "N:AM%dSDmzrIFW}~M8g)"
WAIT_UNTIL_HEAD = "TTZpkvf7P=QPVwWSLcQ7"
LAST_STMT = "85IlD+FNFUd[^xJOS9Yx"  # rightlightstate = 'off'

assert light[HAT]["opcode"] == "control_start_as_clone"
assert light[HAT]["next"] == WAIT_UNTIL_HEAD
assert light[LAST_STMT]["next"] is None

# Bug 1: missing Forever wrapper -- the right light can only ever be used
# once per game session (the script just ends after the first use, never
# loops back to wait for another click).
forever = new_block(light, "control_forever", HAT, {"SUBSTACK": [2, WAIT_UNTIL_HEAD]}, tag="lightforever")
light[WAIT_UNTIL_HEAD]["parent"] = forever
light[HAT]["next"] = forever

# Bug 2: missing "wait until mouse released" debounce -- same class of bug
# fixed on the right door earlier this session. Without it, a single
# physical click spanning multiple frames can re-trigger the toggle.
mousedown_block = new_block(light, "sensing_mousedown", None, {}, tag="lightmousedown")
not_block = new_block(light, "operator_not", None, {"OPERAND": block_ref_bool(mousedown_block)}, tag="lightnot")
light[mousedown_block]["parent"] = not_block
wait_release = new_block(light, "control_wait_until", LAST_STMT, {"CONDITION": block_ref_bool(not_block)}, tag="lightwaitrelease")
light[not_block]["parent"] = wait_release
light[LAST_STMT]["next"] = wait_release

bb_check(light, "Light")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v10) written.")
