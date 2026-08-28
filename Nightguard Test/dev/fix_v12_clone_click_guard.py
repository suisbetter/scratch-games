import json
import sys
sys.path.insert(0, ".")
from block_builder import new_block, add_setvar_literal, add_equals, add_if, str_lit, var_ref, check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
door_target = next(t for t in data["targets"] if t["name"] == "Door")
door = door_target["blocks"]

# ---------------------------------------------------------------------------
# Bug: the right door is a clone of the left door's sprite. Scratch runs every
# hat script a sprite owns independently for each clone too, including plain
# `when this sprite clicked` -- not just `when I start as clone`. The clone's
# own dedicated click-handling script (WHEN_CLONE_CLICK below) correctly
# toggles `rightdoorstate`, but the sprite's *other* `when this sprite
# clicked` hat (WHEN_SPRITE_CLICKED, written for the left door) also fires
# whenever the clone itself is clicked, since it's inherited unmodified --
# incorrectly toggling `leftdoorstate` and broadcasting "left door" on every
# right-door click. That's the actual cause of "clicking the right door
# closes both doors" and the right door's animation looking rushed (two
# Office broadcast handlers race to set the same sprite's costume).
#
# Fix: add a this-sprite-only variable `is clone`, set to '1' as the first
# statement of the clone's own click-handling `when I start as clone` script,
# and guard the inherited `when this sprite clicked` hat so it stops
# immediately when running on a clone.
# ---------------------------------------------------------------------------

WHEN_SPRITE_CLICKED = "bLmg7{PQ|g!kc$VSIpwg"
WHEN_CLONE_CLICK = "oDChRUr%CEVF~ln_?s!G"   # WhenIStartAsClone -> switch costume2 -> Forever{...}
WHEN_GREEN_FLAG = "7^;FDt{O6}Y9j56BKAOB"

assert door[WHEN_SPRITE_CLICKED]["opcode"] == "event_whenthisspriteclicked"
assert door[WHEN_CLONE_CLICK]["opcode"] == "control_start_as_clone"
assert door[WHEN_GREEN_FLAG]["opcode"] == "event_whenflagclicked"

IS_CLONE_VAR = "zNGisCloneVar0001"
door_target.setdefault("variables", {})[IS_CLONE_VAR] = ["is clone", "0"]

# 1) Explicit init on the original (green flag), matching this sprite's
#    existing style of explicitly setting its own state at the top.
old_first_after_flag = door[WHEN_GREEN_FLAG]["next"]
init_block = add_setvar_literal(door, WHEN_GREEN_FLAG, "is clone", IS_CLONE_VAR, "0")
door[init_block]["next"] = old_first_after_flag
door[old_first_after_flag]["parent"] = init_block
door[WHEN_GREEN_FLAG]["next"] = init_block

# 2) Mark this instance as a clone, first thing the clone's click-handler
#    script does (before it switches costume / enters its click loop).
old_first_after_clone_hat = door[WHEN_CLONE_CLICK]["next"]
mark_clone_block = add_setvar_literal(door, WHEN_CLONE_CLICK, "is clone", IS_CLONE_VAR, "1")
door[mark_clone_block]["next"] = old_first_after_clone_hat
door[old_first_after_clone_hat]["parent"] = mark_clone_block
door[WHEN_CLONE_CLICK]["next"] = mark_clone_block

# 3) Guard the inherited left-door click hat: `If (is clone == '1') { Stop
#    (this script); }` before its existing body.
old_first_click_body = door[WHEN_SPRITE_CLICKED]["next"]
stop_block = new_block(door, "control_stop", None, {}, fields={"STOP_OPTION": ["this script", None]}, tag="stop")
door[stop_block]["mutation"] = {"tagName": "mutation", "children": [], "hasnext": "false"}
eq_block = add_equals(door, None, var_ref("is clone", IS_CLONE_VAR), str_lit("1"))
guard_if = add_if(door, WHEN_SPRITE_CLICKED, eq_block, stop_block)
door[eq_block]["parent"] = guard_if
door[stop_block]["parent"] = guard_if
guard_if_block = door[guard_if]
guard_if_block["next"] = old_first_click_body
door[old_first_click_body]["parent"] = guard_if
door[WHEN_SPRITE_CLICKED]["next"] = guard_if

check(door, "Door")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v12) written.")
