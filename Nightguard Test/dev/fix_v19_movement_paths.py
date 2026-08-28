import json
import sys
sys.path.insert(0, ".")
from block_builder import num_lit, check

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
an = next(t for t in data["targets"] if t["name"] == "Animatronics")["blocks"]

# ---------------------------------------------------------------------------
# Give each animatronic a distinct, nameable movement pattern instead of all
# three sharing the identical +/-2-per-tick jitter. Changes only the per-tick
# offset magnitude at the 6 existing call sites (main loop x3, end-of-game
# tail x3) -- the shared position-tracking/clear-slot/mod-8-wrap machinery
# from prior sessions is untouched.
#
#   man    -- "Rush":   wide jump, Random(-3,3) main / Random(-2,3) tail.
#   women1 -- "Patrol": tight jitter, Random(-1,1) main / Random(0,1) tail.
#   women2 -- "Sweep":  fixed +1 every tick, no randomness -- a steady
#             clockwise loop through CAM1->CAM2->...->CAM8->CAM1..., using
#             the same mod-8 wrap already in place.
# ---------------------------------------------------------------------------

# Base "Letter(4, previous cam X) + <offset>" add blocks, one level below the
# mod-8 wrap machinery, found by descending from each call site's join.
RANDOM_BOUNDS = {
    "lV": (-3, 3),   # main loop: man   ("Rush")
    "lY": (-1, 1),   # main loop: women1 ("Patrol")
    "l%": (-2, 3),   # tail: man   ("Rush")
    "l)": (0, 1),    # tail: women1 ("Patrol")
}

for rand_id, (lo, hi) in RANDOM_BOUNDS.items():
    rand_block = an[rand_id]
    assert rand_block["opcode"] == "operator_random"
    rand_block["inputs"]["FROM"] = [1, [4, str(lo)]]
    rand_block["inputs"]["TO"] = [1, [4, str(hi)]]

# women2 ("Sweep"): replace the Random(-2,2)/Random(-1,2) block reference
# with a literal +1 -- same base-add shape, no randomness.
FIXED_STEP_SITES = [
    ("cA", "l!"),  # main loop: rngwomen2 base add, its Random block
    ("cF", "l+"),  # tail: rngwomen2 base add, its Random block
]
for add_id, old_rand_id in FIXED_STEP_SITES:
    add_block = an[add_id]
    assert add_block["opcode"] == "operator_add"
    assert add_block["inputs"]["NUM2"][1] == old_rand_id
    add_block["inputs"]["NUM2"] = num_lit(1)
    del an[old_rand_id]

check(an, "Animatronics (character movement paths)")
print("Sanity check passed. man=Rush(-3,3/-2,3), women1=Patrol(-1,1/0,1), women2=Sweep(+1 fixed).")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v19) written.")
