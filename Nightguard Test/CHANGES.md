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
12. `fix_v12_clone_click_guard.py` — right-door clone no longer fires the inherited left-door click hat
13. `fix_v13_cleanup.py` — removed dead `index` variable; de-duplicated CamMenu's toggle logic

## Session 2 — clone click-handler bug, and the two previously-deferred cleanups

Reported after the fixes above: the right door's close/open animation looked faster than the
left door's, and closing a door in response to an animatronic sometimes closed *both* doors.
Both turned out to be the same bug.

### Root cause: a sprite's click hat runs once per clone too, not just for the original

The `Door` sprite implements the left door as the original sprite and the right door as a single
clone created once at green-flag time. The clone's own `Control.WhenIStartAsClone()` script
correctly polls for `touching mouse + mouse down` and toggles `rightdoorstate`. But the sprite
also has a plain `WhenThisSpriteClicked()` hat, written for the left door, which toggles
`leftdoorstate`. In Scratch 3.0, **every hat script a sprite owns runs independently for each of
its clones too** — including `when this sprite clicked`, triggered by clicks on that clone's own
position, not just `when I start as clone`. Since the right-door clone was never given a way to
tell it apart from the original, clicking the right door fired *both* handlers in the same tick:
the clone's own loop (correctly toggling `rightdoorstate`) and the inherited left-door hat
(incorrectly toggling `leftdoorstate` and broadcasting a spurious `"left door"`).

That single bug explains both symptoms: `leftdoorstate` flipping on every right-door click is
literally "both doors close on one click," and `Office`'s `"left door"` and `"right door"`
broadcast handlers then run as two threads racing to set costumes on the same sprite through
their own `Control.Wait(0.01)` sequences — the spurious left-door thread stomping on the
legitimate right-door animation mid-sequence is what made the right door's close/open look
truncated/rushed. The `Control.Wait` durations on both sides were already equal; there was no
separate timing-constant bug.

This gap existed because the previous session's own door-matrix test simulated a right-door
click by running only the clone's if/else block directly — it never modeled that the real engine
also fires the sprite's other click hat, so this exact bug was invisible to that suite. Confirmed
by reproducing it against the pre-fix `project.json`: simulating a real right-door click (running
both handlers, as the engine actually would) left `leftdoorstate == 'closed'` and produced a
`"left door"` broadcast neither the player nor the right-door handler ever asked for.

**Fix:** added a this-sprite-only variable `is clone` to `Door` (`'0'`/`'1'`, matching this
project's existing boolean-string convention). Set to `'1'` as the first statement of the clone's
click-handling `WhenIStartAsClone()` script, and to `'0'` explicitly in the green-flag hat. Guarded
the inherited `WhenThisSpriteClicked()` hat with `If (is clone == '1') { Stop(this script); }`
before its existing body, so it no-ops immediately when it's actually running as the clone's
inherited copy.

### Cleanup: the two items the previous session deferred

- **`index` (Door.txt).** Was already dead: a global variable set to `'0'` once and incremented
  only by a `data_changevariableby` block with no hat above it (confirmed unreachable, and
  `grep -rn "index" scripts/` found no reads anywhere). Rather than leave it parked, removed it
  entirely — the orphaned increment block, the `index = '0'` initialization, and the global
  variable declaration.
- **CamMenu.txt duplication.** The `WhenThisSpriteClicked()` and `WhenKeyPressed(space)` handlers
  each ran an identical `Control.Wait(0.1)` + two `If (menucounter == ...)` sequence. Factored the
  shared body into a new no-arg custom block, `toggle cam menu`, called from both hats.

### Testing

Added to `run_all_tests.py`: a test that simulates a right-door click the way the real engine
actually processes it (running both the clone's handler *and* its inherited `WhenThisSpriteClicked`
copy, with `is clone` set as the clone's copy would see it) and asserts `leftdoorstate` is
untouched and no `"left door"` broadcast fires — plus the inverse case confirming a real left-door
click (the original, not a clone) still works normally. Also added a test confirming CamMenu's two
trigger paths (click vs. space key) still produce identical broadcasts/costume changes after being
merged into the shared procedure. All prior tests still pass unmodified — this pass was purely
additive.

## Session 3 — power drain was still broken above 99%, and door timing consistency

Reported after session 2: power was "still broken," and doors were "still glitchy" with
transitions sometimes skipped and clicks feeling inconsistently laggy on both sides.

### Power: a real, severe bug that ad hoc testing never triggered

`Animatronics.txt`'s green-flag script sets `power = '100%'` at game start — the actual runtime
starting value every time the green flag is clicked, consistent with this project's established
pattern of every stateful variable (door states, `counter`, `reset`) being explicitly reset by its
owning sprite's own green-flag script even though `Stage` also carries a stale saved default for
each of them (`Stage`'s `power = 95%` is one such stale snapshot, not a value anything actually
applies at runtime).

But `Office`'s power-drain loop assumed power is *never more than 2 characters*: `If (Length(power)
== '2') { <1-digit extraction> } Else { <take exactly the first 2 characters> }`. At `power =
'100%'` (4 characters), that falls into the "2-digit" branch and reads only `"10"` — dropping the
third digit — then decrements to `"9%"`: an instant ~91-point collapse on the very first tick (6
seconds into the game). Confirmed by running the actual patched `project.json` through
`interpreter.py` starting from `"100%"`: the first several `SET power` values were `'9%', '8%',
'7%', '6%', '5%'...`, reproducing the collapse exactly. The 95%-vs-100% gap between `Stage`'s stale
default and the real starting value is exactly why this went unnoticed in casual play and in the
previous session's own tests (which only exercised `"95%"`, `"10%"`, `"1%"`, `"2%"` — never the
real 4-character starting value).

Fixed by replacing all three duplicated length-branching extraction blocks with one direct
expression, `power = Join((power - 1), '%')`. Scratch's arithmetic operators already coerce a
string like `"100%"` to its leading numeric value automatically (the same coercion this project's
original, unmodified time-of-day logic always safely relied on, per session 1's notes) — so the
digit-length branching was unneeded complexity that also happened to be the bug. Works correctly
for any digit count, eliminating this bug class rather than special-casing a third length.

### Doors: re-verified there's no left/right logic asymmetry; the wait *value* was the problem

Re-checked every door state-transition branch (right closing, right reopening, left closing, left
reopening) wait-by-wait: all are already structurally symmetric between left and right (closing is
always 2×`Control.Wait`, reopening is 1 or 2× depending on the other door's state, identically on
both sides). Also re-checked for a power-style conflicting-initializer bug — none found; `counter`
and both door states are each set by exactly one green-flag script, matching `Stage`'s defaults.

Every door-transition wait was `0.01s` — at or below a single real rendered frame (30fps ≈ 33ms,
60fps ≈ 16.7ms). Whether the transition costume and the input-polling tick actually land inside
that 10ms window varies by machine/framerate/load, which reads as "inconsistent" rather than a
deterministic bug, and matches both reported symptoms (transitions sometimes skipped; clicks
feeling laggy in an inconsistent, not-always-the-same-side way). Bumped all 10 door-transition
waits (5 per door handler) from `0.01s` to `0.05s` — about 3x margin over even a 60fps frame, still
reading as instant to a human. This is a value change grounded in how Scratch/TurboWarp's frame
loop works, not something provable via `interpreter.py` the way the other bugs were — it treats
every `wait` as an instant no-op with no concept of real frame timing.

### Testing

Added `"100%"` (open and closed) to the power test matrix, plus a dedicated check that the first
decrement from `"100%"` lands on `"99%"` rather than a truncated jump like `"9%"` — the general
"reaches exactly 0% eventually" check alone wouldn't have caught this, since `100→9→8→...→0` still
terminates at exactly `"0%"`, just via far fewer ticks than it should. All prior tests still pass
unmodified.

## Session 4 — animatronic spawn fairness + an AI toggle for testing

Requested: make each animatronic have an equal chance of spawning, and add a variable/block to
toggle the AI on/off for manual testing.

### Not actually random at all

The initial spawn (`Animatronics.txt`'s third green-flag script) was hardcoded:
`Call rng man('CAM4'); Call rng women('CAM3'); Call rngwomen2('CAM5');` — every animatronic started
at the same camera every game, and since each `rng *` procedure only jitters ±1 from its target,
the three spawn points always clustered in the CAM2-CAM4 band; CAM6/7/8 could never be anyone's
start. Changed each call's argument to `Join('CAM', Random(1,8))` — each animatronic's start camera
is now uniformly 1-of-8, independently.

### A deeper, previously-undetected bug: position tracking drifted from reality

While tracing the spawn/movement math, found that all three `rng man %s` / `rng women %s` /
`rngwomen2 %s` procedures clobber their own position-tracking variable (`previous cam man` /
`previous cam woman` / `previous cam woman2`) with this call's *pre-jitter target*, immediately on
entry — before the procedure's own internal manlist/womanlist/woman2list random pick decides the
animatronic's *actual* final position:

```
goto man = goto              // this call's raw target
previous cam man = goto man  // <- clobbered here, before the real final position is known
...
goto man = manlist[...]      // the *actual* new position (target +/- 1)
...
List.ReplaceItem(camlist, Letter('4', previous cam man), goto)  // "clear old slot" -- but
                                                                  // previous cam man is the
                                                                  // pre-jitter target, not the
                                                                  // real old position
```

That variable is read for two different things — which camlist slot to clear, and (by the caller
on the *next* call) where to move from next — and by the time either happens it already holds the
wrong value. Confirmed with `interpreter.py`: running the movement loop repeatedly, `camlist` froze
after the first move and the tracked reference point fed back into itself instead of the
animatronic actually wandering. `rng women` (women1) doesn't even attempt a clear step at all — it
has only one `List.ReplaceItem` call — so women1's old markers *always* piled up; `rng
man`/`rngwomen2` at least attempted a clear, of the wrong slot. Net effect: stale "occupied"
markers accumulated in `camlist` at different rates per animatronic, biasing whose presence
"stuck" at a door camera over a real game — a second, more insidious way spawning ended up unequal
between the three, on top of the fixed-spawn issue above.

Fixed by reordering (same shape in all three procedures): the "clear old slot" step now runs first,
using the tracking variable's value from *before* this call touches it (the animatronic's true
incoming position); the tracking-variable update now happens *after* the new slot is marked, using
the real final post-jitter position. Added the missing clear step to `rng women` to match.

### A second latent bug this fix exposed: unbounded random walk

Fixing the tracking bug has a real consequence: the movement loop now performs a *genuine*
unbounded ±2-per-tick random walk (previously it wasn't really wandering — it kept getting dragged
back toward the caller's own recent target by the clobbering bug above). Nothing ever clamped the
result to the valid CAM1-8 range. Reasoning about the variance of a ±2 uniform step over a
normal-length game's worth of ticks (tens to 100+) shows the typical drift is much larger than the
8-wide valid range — confirmed directly: `interpreter.py` produced `"CAM0"` and other invalid
camera numbers within a handful of iterations once the tracking fix was in place. This wasn't a bug
*introduced* by the fairness fix — it was always latent, just hidden by the other bug's accidental
"stickiness." Also present in each procedure's own internal ±1 jitter (the manlist mechanism), not
just the caller-side offset — both layers needed the same treatment.

Fixed by wrapping every raw camera-number candidate with mod-8 normalization,
`(((raw - 1) mod 8) + 1)`, at all 12 sites (3 animatronics × [caller-side offset + 2 internal
jitter picks] × [main loop + end-of-game tail]). Chose wrap-around over clamp-to-edge deliberately:
clamping would pile extra probability onto CAM1/CAM8 (whichever edge is hit), undermining the
actual "equal chance" goal; wrapping keeps the walk uniform over the 8 positions. Scratch's `mod`
(confirmed via this project's own `interpreter.py`, which mirrors real Scratch's floored-mod
semantics) always returns a non-negative result for a positive divisor, so this is safe for
negative raw values too.

### AI toggle

Added a global variable `ai enabled` (`'1'` default) and a no-arg custom block `Toggle AI Mode` in
`Animatronics` (flips it), bound to `WhenKeyPressed('t')` as well as being directly clickable in
the editor. The movement loop's three `Call rng ...` lines are gated with
`If (ai enabled == '1') { ... }` — toggling off freezes animatronics in place (camlist keeps
whatever it last had) until toggled back on. Spawn and the end-of-game "one last move" tail are
intentionally left ungated — the toggle is for pausing an already-running game to test other
systems, not for preventing spawn.

### Testing

Added to `run_all_tests.py`: a fairness check running 50 movement iterations from *staggered*
starting positions per animatronic (same starting position for all three would make them compute
identical moves under the interpreter's deterministic `pick random` and mask real bugs behind
coincidental overwrites) asserting each animatronic occupies exactly one `camlist` slot matching
its tracked position, with no stale duplicates — exactly the invariant the old code violated. A
structural check that all 3 spawn calls actually draw from `Random(1,8)`. And a toggle check that
`ai enabled = '0'` makes the movement loop body a no-op while `'1'` lets it proceed. Reproduced the
pre-fix bugs directly against the actual patched `project.json` before fixing them, same as prior
sessions — not just reasoned about in prose. All prior tests still pass unmodified.

### Process note: TurboWarp re-saves invalidate hardcoded block ids again

The `.sb3` had been re-saved by TurboWarp again since the previous session (same as once before) —
confirmed via block counts and `meta.platform` — which regenerates every block id (but not
variable/list ids). All of this session's and `run_all_tests.py`'s hardcoded block ids had to be
re-derived against the actual current file rather than trusted from memory; added
`dev/find_block_ids.py` to do this by structural signature (opcode + which stable variable/list id
a block references) so this is mechanical instead of manual next time.

## Session 5 — the power fix from session 3 was itself wrong, plus character movement paths

Reported: power still randomly skips to `-1%`. Also requested: a distinct, describable movement
path per animatronic.

### The power fix shipped in session 3 was never actually correct

Traced this by re-deriving real Scratch's actual numeric coercion instead of trusting this
project's own test tool. `Cast.toNumber` in scratch-vm is JavaScript's `Number(value)` with
`NaN -> 0`, and `Number()` requires the **entire** trimmed string to be numeric — `Number("50%")`
is `NaN`, not `50`; a trailing `%` makes the whole string non-numeric, not just the suffix. So
session 3's `power = Join((power - 1), '%')` actually evaluates, every single time, as
`toNumber("50%") - 1` = `0 - 1` = `-1` → `"-1%"` — not "eventually" or "unpredictably" in the code,
it's every decrement, unconditionally; "randomly" from the player's side just meant "as soon as a
door closes and a tick actually runs," since players don't see the exact percentage at the moment
it happens.

This passed session 3's own tests because **this project's own `dev/interpreter.py::to_number` was
wrong**: it had a fallback that regex-extracts a *leading numeric run* from a string (`"100%"` →
`100`), which is not what real Scratch does. That's the entire reason the session-3 fix looked
correct in `run_all_tests.py` and still broke in real play — the test tool itself didn't match the
engine it was supposed to be modeling. Fixed `to_number` first (removed the fallback entirely, so
a non-fully-numeric string is `0`, full stop) and re-ran the suite specifically to see what it
would newly expose, before touching any game logic.

This also retroactively explains why the *original*, pre-session-1 project always extracted digits
with `Letter`/`Join` before doing arithmetic on `power`/`time` instead of operating on the full
variable directly — that wasn't incidental style, it's the only way to strip a non-numeric suffix
(`%`, `" AM"`) before arithmetic in real Scratch. Session 3's "simplification" removed that
extraction entirely and broke on exactly the case it existed to handle.

**Fix:** rewrote the power loop's 3 decrement sites back to `Letter`/`Join` digit extraction —
but, unlike the *original* pre-fix code (which only handled 1-vs-2-digit and broke at `"100%"`),
this one handles 1, 2, or 3 digits (power's real domain is `0`-`100`, confirmed by `Animatronics`'
own green-flag reset). Added a full sweep test: every starting value `1`-`100`, door open and
closed, asserting the *entire sequence* of intermediate values never goes negative, not just that
the final value hits `"0%"` — a weaker "reaches 0% eventually" check wouldn't have caught this
class of bug, since real Scratch's string-equality fallback can make a broken sequence still
terminate.

Fixing the interpreter also exposed two unrelated **test-harness** bugs (not product bugs): the
time-cycle and animatronic-fairness tests were silently reading `time`/`ai enabled` from `Stage`'s
serialized defaults, which are just whatever those variables happened to be when the project was
last saved in the editor (this session's `.sb3`, e.g., had `ai enabled = 0` because it was saved
mid-test after the toggle had been used, and `time = '1 AM'` from a mid-game snapshot) — not real
starting values. Both tests now set their own state explicitly first, same as the power test
already did, so they can't silently drift with whatever the file happens to contain.

### A real bug the new fairness testing found (not user-reported)

While hardening the fairness test with the corrected interpreter, found that each `rng *`
procedure's "clear old slot" step (session 3) can wipe out a *different* animatronic's brand-new
mark: if animatronic B's fresh position this tick happens to equal animatronic A's *old* position,
and B is processed after A (fixed order: man, then women1, then women2), B's clear step — still
keyed off *its own* old position — overwrites the slot A just wrote into. Reproduced directly:
man moving to `CAM8` while women1's old position was also `CAM8` made women1's own clear step erase
man's fresh `"man(CAM8)"` mark down to a bare `"CAM8"`. Fixed by guarding each clear step with
`Contains(camlist[...], ownTag)` — the same pattern `Office`'s own jumpscare detection already
uses elsewhere in this project — so a clear only fires if the slot still holds *this*
animatronic's own tag.

**Known, pre-existing limitation left as-is:** `camlist` can only hold one occupant string per
slot. If two animatronics land on the *exact same* camera in the same tick, only the
last-processed one's mark survives (currently always `women2`) — this predates every session's
changes and isn't something the clear-slot guard above can fix without redesigning the list format
to support multiple occupants per slot, which is out of scope here. `run_all_tests.py`'s fairness
check explicitly accounts for this rather than silently ignoring it.

### Character-specific movement paths

Each animatronic previously shared the identical `Random(-2,2)` per-tick jitter. Changed only the
offset magnitude at each animatronic's 2 call sites (main loop + end-of-game tail), leaving the
shared tracking/clear-slot/mod-8-wrap machinery untouched:

- **`man` — "Rush":** wide jump, `Random(-3,3)` main loop / `Random(-2,3)` tail. Covers the most
  ground per tick, least predictable.
- **`women1` — "Patrol":** tight jitter, `Random(-1,1)` main loop / `Random(0,1)` tail. Stays
  local, small drifts.
- **`women2` — "Sweep":** fixed `+1` every tick, no randomness at all (both main loop and tail) —
  a steady, predictable clockwise loop through `CAM1 -> CAM2 -> ... -> CAM8 -> CAM1...`, using the
  same mod-8 wrap already in place. This is also *why* the same-camera-collision limitation above
  became more visible in testing: a full deterministic sweep through all 8 cameras is much more
  likely to cross paths with a wandering animatronic than another random walker was.

### Testing

Added a full power sweep (see above), a structural check confirming each animatronic's offset
block has the intended shape (`man`/`women1` are `operator_random` with the right bounds,
`women2`'s offset is a plain literal `+1`, no `Random` block at all) rather than relying on the
interpreter's deterministic `pick random` (which returns a fixed midpoint per call and can't
distinguish range width from a single sample), and hardened the fairness check to explicitly
account for the same-camera-collision limitation instead of treating it as a pass/fail signal it
was never designed to resolve. All prior tests still pass.

## Fix scripts, continued

14. `fix_v14_power_digits.py` — power-drain digit extraction now handles any digit count (fixes the `"100%"` collapse) — **superseded by v17, see below**
15. `fix_v15_door_wait_duration.py` — bumped door-transition waits from 0.01s to 0.05s for consistent rendering
16. `fix_v16_animatronic_fairness.py` — randomized spawn, fixed position-tracking drift, bounded the random walk to CAM1-8, added the `ai enabled` toggle
17. `fix_v17_power_real_coercion.py` — power decrement rewritten as real 1/2/3-digit `Letter`/`Join` extraction, replacing v14's `power - 1` shortcut that only worked under this project's own (now-fixed) inaccurate test interpreter
18. `fix_v18_camlist_clear_guard.py` — guarded each `rng *` procedure's clear-old-slot step so it can't erase a different animatronic's fresh mark
19. `fix_v19_movement_paths.py` — gave `man`/`women1`/`women2` distinct movement patterns ("Rush"/"Patrol"/"Sweep")

## Session 6 — Phone Guy voice calls (feature, not a bug fix)

Requested: an AI voice based on the FNAF 1 Phone Guy for the Nightguard Test, with
the classic triggers — a night-start greeting, hourly tips, and animatronic
warnings when something shows up outside a door.

### The voice clips

Generated end-to-end by a script (`dev/gen_phone_audio.py`) rather than shipped
as pre-recorded files: **edge-tts** (Microsoft's neural AI voices, no API key)
with `en-US-GuyNeural`, slowed ~10% for the calm, slightly world-weary cadence.
Each clip is then run through a **telephone bandpass** (~300 Hz–3.4 kHz,
scipy `butter`/`lfilter`) so it sounds like the FNAF phone calls — a voice on a
landline — and encoded as a small 48 kHz mono mp3 (lameenc). Output goes to
`dev/phone_audio/` (gitignored; regenerated with `python gen_phone_audio.py`).

**All dialogue is original, written in Phone Guy's *style* — no lines copied
from the game** (avoids embroidering the existing DMCA-flagged FNAF assets any
further than the user-approved rip already does). 10 clips:

1. **Greeting** (plays ~2s after green flag): "Uh, hello? Hello hello! …"
2. **Hourly tips `1 AM`–`5 AM`**, one per hour.
3. **Four random warning clips** fired when an animatronic is spotted outside an
   open door.

### Wiring (`dev/install_phone_guy.py`)

- New **hidden `PhoneGuy` sprite** (1px invisible costume) owns all 10 mp3s plus
  three scripts: the greeting, a sequential `Wait Until (time == 'N AM')` chain
  for the hourly tips (the existing `time` clock already ticks every 60s), and
  the warning handler.
- The warning handler sets sprite-local `warning = pick random(1, 4)` then runs
  four `If (warning == N) { play warning N until done }` branches. It plays with
  **`play sound until done`**, which matters beyond style: while that handler is
  busy, a re-broadcast of `phone warning` can't restart it (Scratch drops events
  into already-running scripts), so a linging animatronic re-triggers a new
  warning only when the previous one finishes — no per-frame audio spam.
- **Office's existing detection handler** (the `forever` broadcasts that already
  play the ambience when an animatronic is outside an open door) now also
  broadcasts `phone warning` right after each ambience sound, in both the left
  and right door branches.
- The new broadcast `phone warning` is registered on Stage; the new sprite-local
  variable `warning` lives on PhoneGuy.
- No game logic changed: power/time/doors/animatronics are untouched.

### Tooling additions

- `dev/repack_sb3.py` now also copies newly staged `<md5>.mp3` / `<md5>.svg`
  files from `dev/phone_audio/` into the sb3 zip (the layout assets are named by
  their content md5, matching how Scratch stores sounds/costumes).
- `dev/interpreter.py` gained `math_number` (a literal reporter) and
  `sound_playuntildone` (no-op, same as `sound_play`) so it can run the new
  PhoneGuy blocks honestly; `run_all_tests.py` gained a **Test 9** that asserts:
  PhoneGuy is hidden with exactly 10 clips + 1 costume and exactly 3 top-level
  scripts, that Office has exactly 2 `phone warning` broadcasts each sitting
  directly on an ambience `sound_play`, that the warning handler executes to a
  valid `1`–`4` pick under the interpreter's deterministic midpoint random, and
  that the full chain fires (animatronic at cam 1 + left door open →
  `phone warning` broadcast). All prior tests still pass unmodified.

### Reproducing this session

```
python gen_phone_audio.py      # regenerate the 10 voice clips
python install_phone_guy.py    # apply the sprite + Office wiring to a fresh extract
python regen_scripts_txt.py PhoneGuy Office
python repack_sb3.py           # put it all back in ../sb3/1287939979.sb3
```
