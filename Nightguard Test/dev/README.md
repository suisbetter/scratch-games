# Dev tooling

Scripts used to build and verify the fixes described in `../CHANGES.md`. These operate directly on
the project's `project.json` block graph (the `.sb3` is a zip containing it) rather than through the
Scratch GUI.

## Reproducing the fixes

```
mkdir nightguard_extract
# extract project.json from ../sb3/1287939979.sb3 into nightguard_extract/
python fix_nightguard.py
python fix_v2_office_gate_reorder.py
python fix_v3_door_state_before_broadcast.py
python fix_v4_right_door_debounce.py
python fix_v5_both_doors.py
python fix_v6_timing_qa.py
python fix_v7a_power_time.py
python fix_v8_animatronics_ai.py
python fix_v9_jumpscare_gate.py
python fix_v10_light_bugs.py
python fix_v11_redundant_cleanup.py
python fix_v12_clone_click_guard.py
python fix_v13_cleanup.py
python fix_v14_power_digits.py
python fix_v15_door_wait_duration.py
python fix_v16_animatronic_fairness.py
python fix_v17_power_real_coercion.py
python fix_v18_camlist_clear_guard.py
python fix_v19_movement_paths.py
```

If a `fix_*.py` or `run_all_tests.py` run fails with a `KeyError` on a block id, the project has
likely been re-saved by TurboWarp since the ids in this repo's scripts were captured — TurboWarp
regenerates every block id (but not variable/list ids) on save. Run `python find_block_ids.py`
against a fresh extraction to re-derive the constants `run_all_tests.py` needs (it finds them by
structural signature — opcode plus which stable variable/list/broadcast id they reference — not by
remembered id), and update individual `fix_v*.py` scripts' hardcoded ids the same way if needed.

After the fix scripts, regenerate the docs and repack:

```
python regen_scripts_txt.py Door CamMenu Office Animatronics
python repack_sb3.py
```

Each script edits `nightguard_extract/project.json` in place and re-validates block-graph integrity
(every `next`/`parent`/input reference resolves to a real block) before writing. Run them in this
exact order against a **fresh** extraction of the original `project.json` — several later scripts
assume specific block ids created or rewired by earlier ones.

## Running the tests

`interpreter.py` is a small from-scratch interpreter for the subset of Scratch 3.0 opcodes this
project uses, built to run the *actual* patched block graph rather than re-simulate expected
behavior. `to_number` mirrors real Scratch's `Cast.toNumber` (JavaScript's `Number(value)`, NaN ->
0) exactly -- the *entire* trimmed string must be numeric, so `"50%"` and `"12 AM"` are `0`, not
`50`/`12`. Don't add a "parse a leading numeric run" fallback here even though it's tempting: an
earlier version of this file had one, which let a real bug (arithmetic done directly on a
`"N%"`-style string instead of stripping the suffix with `Letter`/`Join` first) pass this suite
while still breaking in the real engine -- see `CHANGES.md`'s session-4 writeup. `pretty_print.py` renders block graphs as readable pseudocode (used by
`regen_scripts_txt.py` to regenerate `../scripts/*.txt`). `block_builder.py` has the
block-construction helpers the `fix_*.py` scripts use. `repack_sb3.py` writes
`nightguard_extract/project.json` back into `../sb3/1287939979.sb3`, copying every other zip entry
(costumes/sounds) byte-for-byte. `regen_scripts_txt.py` only handles sprites with real block
scripts (it uses `pretty_print.py`'s generic block dumper) -- `Stage.txt` has no blocks (it's the
Variables/Lists/Costumes/Sounds listing) and needs hand-editing if `Stage`'s variables or lists
change; running `regen_scripts_txt.py Stage` will blank out its Variables/Lists sections.

```
python run_all_tests.py
```

covers the door open/close matrix, power drain at every digit count with doors open/closed, the
12 AM–6 AM time cycle, the animatronic movement loop, the per-door jumpscare gate, that the
reconnected animatronic AI is reachable via real green-flag hat discovery (not just a remembered
block id — this exact class of bug, a new hat created with `topLevel: False`, was caught by this
check during development), that a right-door click cannot also fire the sprite's inherited
left-door click hat (real Scratch clone semantics — see `CHANGES.md`), that CamMenu's two
toggle-menu entry points still behave identically after being merged into one shared custom block,
that power decrements correctly from its real starting value `"100%"` (not just the 1-2-digit
range the original digit-length extraction assumed), that each animatronic's position-tracking
variable stays in sync with `camlist` (no stale wrong-position markers) across 50 movement
iterations from staggered starting positions, that the initial spawn draws uniformly from
`Random(1,8)` instead of a fixed camera, that the `ai enabled` toggle actually gates movement, that
power reaches exactly `"0%"` with no negative intermediate across every starting value 1-100 (open
and closed), and that each animatronic's per-tick offset structurally matches its intended
movement path (`man`=wide random, `women1`=tight random, `women2`=fixed +1, no randomness).
