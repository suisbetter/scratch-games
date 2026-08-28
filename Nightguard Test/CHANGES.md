# Nightguard Test — bug fixes, cleanup, and jumpscare system

This documents every change made to `Nightguard Test/sb3/1287939979.sb3` in this pass, why, and how
it was verified. All edits were made by scripting the project's `project.json` block graph directly
(the sb3 is a zip; the file is fully re-decompiled to `scripts/*.txt` below to keep the repo's usual
docs in sync) — the Scratch/TurboWarp GUI wasn't used for the edits themselves, only for the earlier
manual bug reports that started this work.

## Session context and one process note

Several of the earliest right-door fixes in this session were applied as one-off interactive edits
and were **not** saved as scripts, which caused a rebuild-from-scratch attempt later in the session
to silently drop them (reproducing bugs that had already been fixed once). Every fix below now has a
corresponding saved script (`fix_v*.py`) so the whole pipeline replays deterministically from the
original `.sb3`. If you need to reproduce or extend this work, replay the `fix_*.py` scripts in the
order listed in the "Fix scripts" section at the bottom, against a fresh extraction of the original
sb3's `project.json`.

## Right door button (Door sprite)

The right door is a clone of the `Door` sprite (the original is the left door). Its click handling
had four separate bugs:

1. **Never actually reopened.** The click handler's `If (rightdoorstate == "closed")` branch (meant
   to reopen the door) never set `rightdoorstate` back to `"open"` and had no `Stop`, so execution
   always fell through to the "close" logic afterward — every click just re-closed the door.
2. **Runaway clone creation.** The click handler called `Control.CreateCloneOf(_myself_)` on every
   click, even though it was already running on a clone — each click spawned another independent
   clone that also listened for clicks, compounding indefinitely.
3. **Office's reopen animation was permanently locked out.** `Office`'s `"right door"` broadcast
   handler gated on `counter == 1` *before* checking door state — once `counter` latched to 1 after
   the first close, every later broadcast (including the one meant to reset it) was stopped
   immediately. Reordered so door state is checked first and `counter` is only a close-animation
   debounce.
4. **Multi-trigger per click.** The click detector was `Wait Until (touching mouse AND mouse down)`
   inside a `Forever` loop with no wait for release — a single physical click can span several
   frames, re-triggering the toggle 2–3 times. Added `Wait Until (Not(mouse down))` after handling
   each click.

Also fixed a race: the reopen branch was broadcasting `"right door"` *before* setting
`rightdoorstate` to `"open"`, so `Office`'s handler could read the stale value; reordered to match
the close branch (state set before broadcast).

## Both doors can now close at the same time

The left door's click handler (and `Office`'s mirrored handler for the left-door visual) used to
refuse to do *anything* whenever the right door was closed — so the two doors could never both be
closed. Removed that cross-lock from both places. The right door never had a symmetric lock, so no
change was needed there.

Wired up the "both doors closed" visuals using assets that already existed but were dead code (an
`//----- Orphaned blocks -----` section in `Office.txt`, confirmed via SVG diffing:
`costume7` = right door slab only, a sibling costume = left door slab only, `costume13` = both slabs,
`costume12` = a shared transition frame): one direction reuses that orphaned block outright; the
other direction (left closes while right is already closed) needed a small mirrored addition since
no orphaned block existed for it. Reopening one door while the other stays shut now correctly lands
on the single-door-closed costume instead of jumping straight to "fully open."

## Door timing made consistent

- Removed a stray, purposeless `Control.Wait(0.1)` at the very start of the left door's click
  handler — confirmed (via a targeted check of every `Sound.Play` and script in `Door.txt`) that
  nothing depended on it; it just made the left door feel ~100ms slower to respond than the right.
- Standardized the right door's own open/close transition-frame waits from `0.001s` to `0.01s`,
  matching the left door and the both-doors-closed animation (previously a leftover 10x
  inconsistency from the original project).
- Added the missing transition frame (`costume12` lead-in) to the two reopen-while-other-still-closed
  animations added above, matching the `switch → wait → switch` pattern used everywhere else in this
  project instead of an abrupt costume snap.

## Power drain logic

The original power-drain loop broke below 10% power: a `Variable.Length(power) == 2` check set a
`stop` flag to halt the main loop, but the same iteration still ran the loop's fixed 2-character
extraction formula on the now-single-digit value first, producing garbage (`"9%"` → `"-1%"`). A
*second*, separate loop then caught that `"-1%"` sentinel and restarted a flat 3-second countdown
that never checked door state again — silently dropping the "closing a door drains power faster"
mechanic for the last 8 percentage points of every game. There was also dead code for 3+ digit power
values, which can never occur (power starts at 95% and only decreases).

Replaced all of it with one loop that re-derives the correct 1-digit-vs-2-digit extraction fresh
before *each* decrement (not once per iteration — a single iteration can cross the digit boundary
when a door is closed and it decrements twice), decrementing once every 6s normally or twice with a
5s gap when either door is closed, with a guard against decrementing past exactly `"0%"`. Verified
this preserves the ~2x drain-rate difference at every power level, not just above 10%.

## Time-of-day logic

Traced by hand: the original letter-arithmetic (`"H AM"` → `"(H+1) AM"`, wrapping `"13 AM"` →
`"1 AM"`) actually works correctly at every hour through Scratch's implicit string-to-number
coercion — no functional bug found. Rewrote it with the same explicit length-aware digit extraction
used for the power fix (for consistency and to stop relying on that implicit coercion), with zero
change to observable behavior — still ticks every 60s, still wraps the same way, still stops exactly
at `"6 AM"`.

## Jumpscare system

**The animatronic AI was never running at all.** `Animatronics.txt`'s initial spawn calls and its
movement loop (`Repeat Until (power == "0%") { move all three animatronics }`) sat in an
"Orphaned blocks" section with no hat block whatsoever — not attached to green flag or anything
else. They had never executed. That means `camlist` (the list `Office` reads to detect an
animatronic near a camera) never got populated, so the partial detection/death system already in
`Office.txt` had nothing to ever detect.

On top of being disconnected, the movement loop's own re-invocation calls had a real bug:
`(previous cam man + Operator.Random(-2, 2))` adds a random offset to the *whole string* `"CAM4"`
instead of extracting the trailing digit first — Scratch coerces the non-numeric string to `0`, so
this would have immediately generated invalid camera names like `"CAM-2"` the moment it ran. Fixed
by extracting the digit with `Operator.LetterOf(previous cam man, 4)` first, matching the pattern
already used correctly elsewhere in the same file, at all 6 call sites (3 in the main loop, 3 in a
second, separately-orphaned "one last move" tail script that got joined onto the reconnected main
script).

Also fixed the per-door gate in `Office`'s detection handler: it used to stop checking *both*
cameras if *either* door was closed, so closing the right door also blinded the left-side camera's
detection. Split into two independent checks, each gated only by its own door — **assumption**:
camera list slot 1 corresponds to the left door's camera, slot 2 to the right door's, since the
camera art is placeholder colored boxes with no left/right labeling and this can't be derived from
assets. This is a one-line swap (which condition gates which camera) if it turns out backwards once
real camera art exists. The original "camera 1 wins if both are simultaneously active" tie-break is
preserved.

With this reconnected and fixed, the full chain now actually works: green flag → animatronics move
toward the office over time → one reaches camera 1 or 2 → `camlist` gets marked → `Office` detects
it (if that camera's door is open) → peek costume + ambience sound → if the door stays open 10s →
`"death"` broadcast → the existing (already-built, previously unreachable) scare sequence fires:
2s pause, `Big Boing.wav`, teleport to center, ghost visual effect, 10 random-position jumps, plus
`Office` resets its costume and `Sprite1` shows itself. No new art assets exist to build a fancier
jumpscare visual from, so none were invented — this wires up exactly what the project already had.

## Light.txt

Found while auditing for "the same bug class elsewhere": the right light's clone click-handler had
both of the bugs the right door had before this session —
1. No `Forever` wrapper, so the right light could be used exactly **once** per game session and then
   never again.
2. No "wait until mouse released" debounce, the same multi-trigger-per-click glitch fixed on the
   right door.

Both fixed the same way as the door.

## Redundant/dead code removed

- `Animatronics.txt`: a fully vestigial, unreferenced `Control.CreateCloneOf(_myself_)` with no
  `WhenIStartAsClone` hat anywhere in the sprite to make use of a clone.
- `Door.txt`: a duplicate `WhenBroadcastReceived(show) { Looks.Show(); }` hat (two identical copies
  existed).
- `Office.txt`: a duplicate, completely empty `WhenBroadcastReceived(left door) { }` hat next to the
  real handler.
- The power-drain sentinel loop and the dead 3+ digit branch described above.

**Left as-is, out of scope:** a pre-existing orphaned `index += 1;` statement in `Door.txt`
(unrelated to anything touched here — the `index` variable isn't used anywhere else either), and
`CamMenu.txt`'s keyboard/mouse handlers duplicating the same open/close logic twice (cosmetic, not a
bug — not worth the risk of touching a working script for a purely stylistic win in this pass).

## Testing

"Run a test yourself" was taken seriously: rather than re-reason about the block graph in prose, a
small interpreter for the actual Scratch opcodes this project uses was built and run directly against
the real, patched `project.json` (not a simulation of expected behavior). A real headless
`scratch-vm` run in Node was attempted first per the original plan, but its install didn't complete
within a reasonable effort (a large, browser-oriented dependency tree) — the hand-written interpreter
was used instead, and is disclosed here rather than glossed over.

This interpreter caught three real bugs during construction of these very fixes, before they ever
reached the user:
- A helper that re-linked an already-linked block silently dropped the `"13 AM" → "1 AM"` wraparound.
- A brand-new Animatronics green-flag hat was created with `topLevel: False` (a copy-paste default),
  which would have made it invisible to the real Scratch engine entirely — caught only because a
  hat-*discovery*-based test was added alongside the manual-block-id tests.
- Two Scratch list opcodes were initially misnamed in the interpreter itself (`data_listadd` vs. the
  real `data_addtolist`), caught immediately by an exception rather than silently mis-simulating.

Final verification (`run_all_tests.py`) covers: the full door open/close matrix in every order
(7 sequences), power drain reaching exactly `"0%"` at every starting digit count with doors open and
closed, the ~2x drain-rate ratio, the full 12 AM→6 AM time cycle, the animatronic movement loop
staying within valid `CAM1`–`CAM8` positions over 15 iterations with well-formed `camlist` entries,
the per-door jumpscare gate's independence (including the exact "only the other door is closed"
scenario that was the actual bug), and that the reconnected AI script is reachable via real
green-flag hat discovery rather than a remembered block id. All pass.

**What this does not cover:** real Scratch's actual random-number distribution (the interpreter uses
a deterministic midpoint for `pick random` so tests are reproducible — this proves the mechanism
produces no invalid states, not that the wandering "feels" random), rendering, audio, and real-time
frame pacing (all `wait` durations are simulated as instantaneous causal ordering, not real delays).
Manual in-editor testing is still worthwhile for feel/pacing/art, but the *logic* has been verified
directly against the real block semantics.

## Fix scripts (apply in this order to a fresh extraction of the original sb3's `project.json`)

1. `fix_nightguard.py` — right door if/else + open-state fix (early version, order fixed by #2/#3) + clone-spam removal
2. `fix_v2_office_gate_reorder.py` — Office right-door counter/state gate reorder
3. `fix_v3_door_state_before_broadcast.py` — set-before-broadcast ordering
4. `fix_v4_right_door_debounce.py` — mouse-release debounce
5. `fix_v5_both_doors.py` — cross-lock removal + both-doors-closed visuals
6. `fix_v6_timing_qa.py` — door timing consistency
7. `fix_v7a_power_time.py` — power/time logic rewrite
8. `fix_v8_animatronics_ai.py` — animatronic AI bugfix + reconnection
9. `fix_v9_jumpscare_gate.py` — per-door jumpscare gate independence
10. `fix_v10_light_bugs.py` — Light.txt Forever + debounce fixes
11. `fix_v11_redundant_cleanup.py` — dead/duplicate handler removal
