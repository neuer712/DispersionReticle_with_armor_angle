# CLAUDE.md

Read this first. It orients you fast; go to the referenced files/docs for detail.

## What this repo is

Base project: **Pruszko's DispersionReticle** (MIT), a World of Tanks Python client mod that adds
extra dispersion reticles. Unmodified structure lives under `src/dispersionreticle/` and
`src/mod_DispersionReticle.py` - see `README.md` for what the *original* mod does.

What we're building on top of it: **Armor Angle HUD** - a new feature, self-contained in
`src/dispersionreticle/armorangle/` plus one hook file and some config wiring, showing a small
on-screen HUD that estimates the player's OWN hull armor incidence angle, assuming a hypothetical
enemy positioned along the current aim direction (a defensive "am I angled enough" tool, not an
offensive penetration calculator - see `HANDOFF.md` for the original design rationale/red lines).

**Read `HANDOFF.md` first** for the original math derivation and scope decisions (still accurate).
**Read `ARMOR_ANGLE_PLAN.md` second** for the v2 design writeup (bilingual EN/CN, written mid-project -
some of it is now historical, but the math derivations in it are still correct and detailed).
This file (`CLAUDE.md`) is the "what's actually true right now" summary; when it conflicts with the
other two docs, trust this one.

## Environment facts (all confirmed, not guesses)

- Target runtime: **Python 2.7** (WoT's embedded interpreter). Installed locally at
  `C:\Python27\python.exe` - use it for everything (compiling, running scratch test scripts).
  `.pyc` magic number byte-for-byte verified against an official release build of this mod.
- The user's WoT install: `G:\SteamLibrary\steamapps\common\World of Tanks\eu\`, client version
  `2.3.1.2`, mods folder `mods\2.3.1.2\`. Client language is English (not Chinese), even though the
  user communicates with you in Chinese - keep in-game HUD text ASCII/English (see "known bugs
  fixed" below for why Chinese text is actually broken on this client, not just a style choice).
- No general-purpose test framework in this repo. The pattern used throughout this project: write a
  small standalone script that does `sys.path.insert(0, r"D:\...\src")` then imports the pure
  (BigWorld-free) modules directly, run it with `C:\Python27\python.exe`. `armor_math.py` and
  `armor_db/` are 100% BigWorld-free by design specifically so this works. Anything touching
  `BigWorld`/`GUI`/`AvatarInputHandler` etc. CANNOT be unit tested here - it can only be verified by
  building, deploying, and having the user test in a training room and read back `python.log`.
- **Important gotcha discovered the hard way**: `python -m py_compile` does NOT catch "non-ASCII
  character but no encoding declared" errors the way `import` does (Python 2 quirk - `compile()` on
  an in-memory string is lenient, but the `import` statement's file-reading path isn't). Never trust
  `py_compile` alone as your syntax gate for a file with non-ASCII content - write a script that
  actually `import`s the module.

## Build & deploy

- `build.bat` - compiles everything, packages `build/pruszko.dispersion_reticle_dev.wotmod`. Calls
  `generate_armor_db.py` automatically as its first step (see "data model" below).
- `deploy.bat` - **user-personal, gitignored**, hardcoded to their WoT path. Calls `build.bat` then
  copies the result into `mods\2.3.1.2\`. This is what actually gets used day to day:
  `cmd /c deploy.bat` (or the user runs it directly). Fails loudly (non-zero exit, clear message) if
  the game is still running and has the file locked - that's expected, not a bug to chase.
- `generate_armor_db.py` - generic codegen, gitignored but NOT personal (reusable). Reads
  `armor_data/*.json` and writes `src/dispersionreticle/armorangle/armor_db/*.py`.
  **These generated `.py` files are marked "DO NOT EDIT BY HAND" at the top - respect that.** Edit
  the JSON, regenerate.
- All four of the above are gitignored (`/*.py`, `/*.bat` are NOT globally ignored anymore though -
  only `/deploy.bat` specifically is; `build.bat`/`build_wotmod.py`/`generate_armor_db.py` ARE
  tracked, since they're reusable project tooling, not personal). Check `.gitignore` if unsure.
- Nothing in this repo gets committed automatically - only commit when explicitly asked.

## Data model (armor_data/*.json -> generated Python)

- `armor_data/vehicles.json`: per-vehicle armor plate data, grouped by nation. Each plate has
  `label`, `bearingDeg` (signed yaw offset from hull forward: 0=front, +90=right side, -90=left
  side), `slopeDeg` (signed tilt from vertical - **sign convention**: positive = plate's top tucks
  INTO the hull / bottom sticks OUT, the "classic glacis" lean, used for upper glacis/side
  upper/pike cheeks by default; negative = the opposite lean, typically lower glacis/side lower,
  forming a "V" against the plate above it - see the long comment in `armor_db/__init__.py`),
  `nominalMm`, and `mirror` (true = both bearingDeg and -bearingDeg get an entry, via
  `mirroredPair()` - needed so turning the hull either way still finds a matching plate; false for
  bearingDeg 0/180 which are self-symmetric).
- `armor_data/tier_thresholds.json`: `{tier: [threshold1, threshold2]}` for HUD color-coding
  (red/yellow/blue by approximate effective mm - see `armor_math.colorCategoryForAssessment` for the
  exact rule, including the deliberately-asymmetric fallback when threshold1 > threshold2). A
  vehicle's own `safetyThreshold1`/`2` in `vehicles.json` override the tier default if BOTH are set.
  **Currently only tiers 7 (180/220) and 8 (230/270) have real numbers** - the rest are `null`
  placeholders (always render blue/neutral until the user fills in real per-tier balance numbers,
  which needs the user's own game-balance judgment, not something to guess).
- Currently whitelisted vehicles (all German): Tiger I (`germany:G04_PzVI_Tiger_I` - name+data
  confirmed live), Tiger II (`germany:G16_PzVIB_Tiger_II` - name+data confirmed live, data was
  hand-provided by the user), E-75 (`germany:G65_E_75` - name AND data still an unverified guess,
  never seen in a live log).

## Runtime architecture (src/dispersionreticle/armorangle/)

- `armor_math.py` - all the actual math, zero BigWorld deps, fully unit-testable. Core function:
  `plateIncidenceDeg(alphaSignedDeg, bearingDeg, slopeDeg, elevationSignedDeg=0.0)` - exact (not
  approximate) 3D dot-product formula `cos(incidence) = cos(slope)cos(elevation)cos(alpha-bearing) +
  sin(slope)sin(elevation)`, independently verified via literal vector math in this project's
  history (see conversation/commit history, not repeated in a file). Also has the 5deg flat
  shell-normalization logic (AP-only; ricochet check uses the RAW un-normalized angle), the
  UI-slot-classification functions (`classifyFrontPlate`/`classifySidePlate`/`UI_SLOTS`), and the
  color-category resolver.
- `armor_db/__init__.py` - `ArmorPlate`/`VehicleArmor` namedtuples, `mirroredPair()` helper,
  `getVehicleArmor()` (lazy per-nation import so only nations actually played get loaded).
- `armor_db/germany.py`, `armor_db/tier_thresholds.py` - GENERATED, don't hand-edit.
- `armor_angle_hud.py` - the only file that touches `GUI`/`BigWorld`. Creates 8 independent
  `GUI.Text` components (one per grid slot: left/right side upper+lower, left/right pike cheek,
  front upper+lower), each at a FIXED screen position computed once at creation
  (`armor-angle.position-x`/`-y` config + per-slot column/row offset) - NOT dynamically tracking the
  reticle (an earlier attempt projected the gun's 3D world position onto screen every tick to follow
  the reticle; this broke badly in sniper mode where the camera sits at ~the gun's position, making
  the projection degenerate - text flew around. Fixed position was the actual fix, confirmed
  working). A slot with nothing to show is just hidden - it never reflows/shifts sibling slots.
- `hooks/armor_angle_hooks.py` - ties `armor_angle_hud.g_armorAngleHud.start()/stop()` to
  `VehicleGunRotator.start/stop` (same lifecycle hook pattern as the base mod's
  `vehicle_gun_rotator_hooks.py`).
- Config: `armor-angle.enabled` (default false), `armor-angle.debug-mode` (default false),
  `armor-angle.position-x`/`-y` (default 0.0 / -0.1, absolute screen position, NOT reticle-relative).
  Also has a garage Mod Configurator page section now (`_createArmorAngle()` in
  `support/mods_settings_api_support.py` + `Tr.ARMOR_ANGLE_*` in `settings/translations.py` +
  `armorAngle.*` keys in `gui/dispersionreticle/translations/translations_{en,zh_cn}.json`).

## Display behavior (as of the last change)

- Non-debug mode (default): each slot shows just `~123mm` (approx effective thickness) or
  `RICOCHET` - no angle number, no plate label (position in the grid identifies which plate).
- Debug mode: two lines, `"%d\n%s %s"` - incidence angle, then PEN/RICOCHET status + mm. This
  multiline format DOES work correctly in this client (an earlier "fix" that collapsed it to one
  line was based on a misdiagnosis - the user's actual bug was elsewhere - and was reverted).
- Colors: red=danger, yellow=warning, blue=safe, and **ricochet is ALSO blue, not purple** - purple
  vs red turned out to be too easy to confuse in peripheral vision during actual play, so ricochet
  was deliberately made visually identical to "safe".

## Known-unverified things (flag clearly if you touch them, don't silently assume they're fine)

- E-75's internal name and armor data (never confirmed against a live client).
- Whether `vehicleTypeDescriptor.type.level` really is the 1-10 tier (a one-time diagnostic log line
  already exists for this in `armor_angle_hud.py` - check `python.log` for
  `"vehicleTypeDescriptor.type.level = ..."` if this needs re-confirming).
- Most tiers still have no color threshold values in `tier_thresholds.json`.
- Nothing beyond German tier 6-9ish heavies has been added to the whitelist - the data model
  supports pike/arrow armor (multiple front plates at nonzero bearing) but no real vehicle using it
  has been entered yet, only synthetic test fixtures.

## Working style established in this project (keep doing this)

- Before claiming anything works, actually verify it: compile with the real Python 2.7, write a
  standalone import-based test script for anything BigWorld-free, and for anything that touches
  BigWorld, build+deploy and ask the user to test in-game and report back `python.log` output.
- When something can't be verified in this environment (most GUI/BigWorld API guesses), say so
  explicitly and give the user a concrete way to verify it live, rather than presenting a guess as
  fact.
- Prefer fixing the actual root cause over a workaround, and prefer asking a clarifying question
  over guessing when a design decision is genuinely the user's call (game-balance numbers, UI layout
  preferences, color semantics) - this user has been very precise/technical throughout and gives
  good, specific answers when asked.
