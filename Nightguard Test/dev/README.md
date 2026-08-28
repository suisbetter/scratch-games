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
```

Each script edits `nightguard_extract/project.json` in place and re-validates block-graph integrity
(every `next`/`parent`/input reference resolves to a real block) before writing. Run them in this
exact order against a **fresh** extraction of the original `project.json` — several later scripts
assume specific block ids created or rewired by earlier ones.

## Running the tests

`interpreter.py` is a small from-scratch interpreter for the subset of Scratch 3.0 opcodes this
project uses, built to run the *actual* patched block graph rather than re-simulate expected
behavior. `pretty_print.py` renders block graphs as readable pseudocode (used to regenerate
`../scripts/*.txt`). `block_builder.py` has the block-construction helpers the `fix_*.py` scripts use.

```
python run_all_tests.py
```

covers the door open/close matrix, power drain at every digit count with doors open/closed, the
12 AM–6 AM time cycle, the animatronic movement loop, the per-door jumpscare gate, and that the
reconnected animatronic AI is reachable via real green-flag hat discovery (not just a remembered
block id — this exact class of bug, a new hat created with `topLevel: False`, was caught by this
check during development).
