# SPRINT-01 development preview

Windows x64 native prototype. This document describes implementation, not
production safety. The research acceptance is COLLISION-SLOPE-07B in
[movement-report.md](reversing/movement-report.md). This archive includes both
the research tools and the unfinished native implementation. The original
research and feature worktrees were preserved separately during publication.

**SPRINT-01B BLOCKED. Do not enable this prototype for normal play.** Left Shift
Hold is now observed requesting and releasing Sprint. In the current save the
native run parameter is 3E2F28C8, rejected 479 times by the unchanged baseline
guard before clip/preflight. L3 remains unresolved. A conservative UI predicate
is implemented; its observed states are documented below, separately from a
successful extra-in-menu inhibition test, which remains blocked.

## Build

Python 3.14 and Git, Zig 0.15.2 for Windows x64. Install the compiler into a
project virtual environment, for example `python -m pip install ziglang==0.15.2`.
No global compiler installation or drivers are needed.

```powershell
python tools/build_native.py --zig .venv/Lib/site-packages/ziglang/zig.exe --config Debug
python tools/build_native.py --zig .venv/Lib/site-packages/ziglang/zig.exe --config Release
```

The script fetches MinHook at `c3fcafdc10146beb5919319d0683e44e3c30d537`
into ignored `.cache/minhook`, checks its commit and clean tree, compiles its C
sources, runs native assertion tests with NDEBUG explicitly undefined, then links
`SAOHRFix.asi`. Outputs and MinHook license are in `.cache/native/<configuration>`.
There is no CMake dependency. Dependencies at runtime are Windows/UCRT, BCrypt,
User32 and XInput 1.4. Downloaded libraries and binaries are not committed.

## Loading, configuration and removal

The existing game directory's `d3d11.dll` identifies itself as Ultimate ASI Loader
x64 8.2.0. The plugin exports `InitializeASI`; DllMain only records its module and
disables thread notifications. Initialization pins the DLL and starts a worker.
Do not replace d3d11.dll, Ultrawide.asi, Special K, EXE or CPK files.

With the game closed, copy `SAOHRFix.asi`, `SAOHRFix.ini` and the MinHook license
from the build directory beside `sao_hr.exe`. Refuse to overwrite an existing
SAOHRFix installation without preserving its config. Launch through Steam.
Require the loader's default `DontLoadFromDllMain=1`. Other loaders and manual
injection are untested. A log file beside the plugin confirms actual loading.

The shipped INI defaults to `enabled=false`, which installs no hooks.
Set `[sprint] enabled=true` explicitly for development testing, then restart.
`mode=hold` requests Sprint while Left Shift or an XInput LeftThumb button is
held. `mode=toggle` changes request on each rising edge. Axes remain untouched.
The first press after focus/connection/identity invalidation requires a release
to arm. Device connection changes clear the toggle conservatively. Any connected
XInput pad can supply L3. Steam Input and mod interception can affect visibility.
No claim is made that L3 is globally unused by the game's bindings.

Only `factor=1.25`, `key=LeftShift`, `button=LeftThumb` and `level=info` are accepted.
Other values disable the plugin with a logged reason. Other numeric factors are
not supported. Config loads once; restart to change it. No live reload or UI.
`[diagnostics] enabled=true` records at most 16 accepted-extra witnesses plus
aggregate movement/animation counts. Normal logs include transitions, reason
codes and counters every five seconds, not individual physics frames.

To disable, close the game and set enabled=false. To uninstall, close it and
remove only SAOHRFix.asi/INI/log and its license. The stop export only switches
to vanilla forwarding; unloading a hooked DLL in a running game is unsupported.
Resident trampolines and unwind tables remain until process exit.

For troubleshooting, preserve SAOHRFix.log alongside the exact INI and build
configuration. disabled_no_hooks is expected with the shipped configuration.
unsupported_build_or_modified_bindings_vanilla means no hooks are installed;
do not relax its hash check. SPRINT-01B activation_snapshot lists named gate
counters as reached/excluded. eligibility_reason is now the Gate ordinal + 1,
with 0 following an accepted extra. Historical SPRINT-01 logs used the four
coarse categories described in the earlier test record. Input flags
encode focus in bit 0, Left Shift in bit 1, L3 in bit 2 and connected XInput slots
from bit 8. A connected controller outside the game need not be visible here.

## Native implementation

`native/sprint.hpp` contains config validation, input edge state and pure XZ
eligibility/calculation. `native/runtime.cpp` supplies loader, hash and binding
validation, discovery, native calls, hooks, synchronization and logging.
`native/tests.cpp` tests config rejection, focus/re-arm, Hold/Toggle, repeated
presses, blocked/projected movement, terrain Y, zero and nonfinite vectors.

The supported EXE SHA-256 is
`1923f0d8d2cad559d6ad6e001af54ea5ea5aa70171323f42d4e1fa3d63699e43`.
Loaded bindings are compared against that disk image before hooking. Modified
entry/body ranges or an unknown image leave vanilla. No upstream speed hook.

MinHook detours 58D340 and 6C6C80. No private gameplay method copies or shadow
vtables are installed. Player discovery uses read-only private-memory scans,
unique CChrPc vptr, physics manager membership and current owner/channel links.
It excludes its own scan buffer. No heap VA or physics ID is hardcoded.
Before extra work, current associations and original instance vptrs are checked
again using ReadProcessMemory. Only the KCC/world received by the engine's
physical callback are invoked. Retained player/channel pointers are read only.

The physical detour saves original requested displacement and ghost position,
calls original 58D340 first, then checks E3=1, FF/FE, F8A6=1/F8AD=0, exact run
bits 3E2BB98D or 3E2D712B and clip122. It preserves the diagnostic tolerances
abs(requestedY)<=.001 and XZ actual/requested error<=.0002. Nonfinite/zero
vectors fail closed. Additional requested Y/W are zero.
The capsule preflight uses the original callback vtable, shape margin handling,
group/mask initialization and native 6F8890. A hit discards the extra.
Clear sweeps submit `(factor-1)*vanillaXZ` with 72A5F0 followed by original
58D340 with dt=0. No second gameplay update, Y clamp or direct ghost write.

A try-lock around the mod's player physical update publishes accepted state only
after the extra completes. Animation uses a shared try-lock and returns vanilla
while physics is in flight. It also requires the current binding, actual channel,
callsite 2888CC, clip122 with checked index, run guards and original return1.0.
Other clips/rates/channels call the original getter. This couples to the latest
completed physical update, not an asserted atomic gameplay/render frame.

The physical trampoline's executed 10-byte prologue allocates 0x118 stack bytes.
The prototype registers matching Windows x64 unwind metadata for those 10 bytes
and its 14-byte return jump, checking the emitted layout before enabling hooks.
Compiler-generated functions retain their ordinary PE unwind data. The getter
trampoline is a leaf. Failures during preparation never enable the hooks.

## Limits that remain to validate

The mod lock does not lock the engine's destruction or object pool. RPM prevents
dereferencing unreadable stale snapshots in the mod; it does not establish a
formal engine lifetime contract or exclude address reuse between checks.
Concurrent destruction, shape sharing and update ordering require live stress
validation before a release claim. No hot unload, general cutscene or combat
classifier is claimed. The limited UI predicate added in SPRINT-01B is described
below. FF/FE is not itself a UI or combat classifier.

The full Python SLOPE-06 catcher is not bundled. Its consumed-return producer
capture remains a separate research instrument; do not combine independent
native/Python hooks in the same process without validating their composition.
The bounded native extra witnesses support comparison of requested/actual
displacement only, not a new consumed-dt classification. Historical integration
outlier remains UNKNOWN, not reproduced. Foot sliding remains unmeasured.

## Test record

### 2026-10-23 — native implementation smoke test

CONFIRMED: Debug and Release compile with warnings treated as errors; assertion
tests run in both configurations, including Release with NDEBUG undefined.
Tests cover config rejection, Hold/Toggle edges, release/rearming after lost
availability, and extra displacement validation. PE exports InitializeASI and
StopSAOHRFix; no Python runtime is required by the plugin.

CONFIRMED runtime: the existing Ultimate ASI Loader loaded the native DLL.
Default enabled=false produced disabled_no_hooks. Enabled launches installed
both resident detours and registered the physical trampoline's unwind table.
An earlier unwind allocation failure stayed vanilla and was corrected before
the successful hook launches. This is not an exception-unwind stress test.

Normal fast travel from town to Poggio Phoeniath caused native association
reacquisition (physics ID 1, transient 2, then 12). Later process launches
reacquired ID 10. Vanilla pad movement and game shutdown/restart worked.
The native log saw a brief Left Shift requested/released transition, but this
does not validate physical keyboard Hold behavior.

CONFIRMED: across the smoke-test log, accepted_extra_total=0,
animation_corrected_total=0, and zero extra witnesses. Therefore no claim is made
for native Sprint speed, playback coupling, collision behavior, or accepted
post-travel Sprint. Research results do not substitute for these native tests.

With SpecialK64/XInput_SK64 present, external XInput polling saw the virtual
pad's L3=64, while native polling saw a connected pad with L3 neutral. In the
comparison launch with global Special K injection stopped and those modules
absent, the game still received pad input but the DLL saw no XInput controller.
This narrows the input incompatibility to the tested input paths; it does not
prove Special K alone causes it. Existing input.md already distinguishes Steam
Input's consumed pad state from raw Windows input. No hook bypass was added.

The main menu permits world movement under left-stick input. FF/FE and window
focus therefore cannot establish menu suppression. No guessed address, Start
latch or relaxed eligibility guard was introduced to conceal this gap.

Blocked live checks: native L3 Hold, physical keyboard Hold, Toggle integration,
accepted 1.25x movement/rate, wall/slope and accepted lifecycle/restart behavior.
No different-FPS validation or driver limiter change was performed. The
historical NVAPI -166 limitation remains; fps:null was not newly verified.

Cleanup: game closed normally, pad reset/disconnected, global Special K services
restored. Only this session's SAOHRFix ASI/INI/log were moved out of the game
directory into ignored .cache/live-sprint-01. Original loader and Ultrawide
remained installed. Game EXE and loader hashes are checked separately below.
No original vptr was exchanged by this implementation; resident detours and
private memory ended with the process. No driver, EXE or CPK writes.

Final checks passed: six research-tool self-checks (including limiter self-check,
not a driver read), Python compilation, both research TOML parses and staged /
unstaged git diff --check in both worktrees. Original research index binary diff
SHA-256 stayed ec8c6d3c459f504050d81cb7796d636176f6cc6d112ed454a31f05a2c092af3a.
The EXE retained the supported SHA-256 above; d3d11.dll retained
bf98a5293ded7278b0e4a41f968e540b44abedad4d17ae459dd372a075848448.

Audio, graphics features and ImGui are absent. Town/combat, engine object
destruction races, physical bindings and mod compatibility remain unvalidated.

## Historical Git handoff

Implementation is isolated in branch sprint-01 at C:/Users/Maicol/SAOHRFix-sprint-01.
The first signed commit failed with `1Password: failed to fill whole buffer`.
No commit was created and no signing setting was changed. SAOHRFix.ini,
native/sprint.hpp and native/tests.cpp remain staged in this worktree; runtime,
build tool and documentation remain separate pending changes. The original
research worktree's index is unchanged; its movement-report header and a new
SPRINT-01 section are unstaged additions to the existing research changes.

## SPRINT-01B — 2026-10-26

**BLOCKED, zero accepted native extras.** A+C, tolerance values, run baseline
bits and clip eligibility remain unchanged. No collision research or new filter.

### Activation evidence

CONFIRMED runtime, final Release launch in Bastione Oltrum: Cordia, current save
Kirito level 49: both hooks installed. The final bounded snapshot records
2,038,897 physical hook entries and 53,611 matching player-KCC entries. Therefore
hook installation and invocation are separately demonstrated. These counts are
calls, not frames, and include native idle work and other controllers.

Physical Left Shift input produced requested/released transitions. One observed
request interval was ticks 41978859..41996109; another was
41998156..41999125. Input polls and physical calls are asynchronous. The first
press at the title screen counted keyboard input but correctly requested no
Sprint without a player/UI context. In exploration the worker published a
request, and release returned it to false. Zero input remained requested during
the final idle period. No controller polling result was needed for keyboard Hold.

During the controlled two-second forward/back impulses while Shift was held:
identity/selector each passed 2,383 calls overall; motion F8A6=1/F8AD=0 passed
479. Every one of those 479 calls next failed the parameter guard. Captured
rejected_parameter_bits=1043278024 = 0x3E2F28C8 = 0.17105400562286377.
Allowed values remain 0x3E2BB98D = 0.16770000755786896 and
0x3E2D712B = 0.16937701404094696. A read-only 12-second vanilla sample also
observed the new bits, including 421 polls with motion 1/0. Cause of the changed
vanilla parameter is UNKNOWN; no level/equipment/buff cause is asserted.

The snapshot's first_exclusion=12 means motion in the initial idle request,
before movement started. The decisive first failed guard *during run* is
parameter. Clip, displacement, preflight and second wrapper were not reached
on these requests. Accepted=0, second_wrapper=0, animation corrected=0; this is
not a preflight rejection and not evidence against A+C's physical behavior.
One matching physical call encountered a busy mod lock and forwarded vanilla.
This localizes the current run exclusion; the coarse October 23 log cannot
retrospectively establish which guard would have failed during a sustained run
request in that earlier save/context.

New diagnostics use fixed atomic bins for reached/excluded counts and first
requested exclusion. Up to 120 snapshots are logged at five-second intervals
when diagnostics are enabled; individual frames are never logged. Native sweep
entry, invalid preparation, hit rejection, second wrapper and animation getter
entry/correction are distinct counters. Existing extra witnesses remain capped
at 16. Final source prints the first exclusion by name; live captures preceding
that formatting change use the ordinal. The added animation_getter entry count
and refined preflight diagnostics are built/tested, not separately live-tested.

### UI guard

CONFIRMED static: 1D2640 constructs the UI bridge stored at game+38; 375870
stores field controller at bridge+0 and CUiModeCharacter at bridge+18. Character
is field+5C8. Expected vtables are 82C268 and 82C438. Native getter 37A2C0 tests
character+28==0; the character menu pointer is character+30.

CONFIRMED read-only runtime with visible main menu, Oggetti inventory and skill
tree: character state=5. Normal gameplay before/after closure: character state=0,
menu pointer null, field state=5. CUiChrMenu itself is dynamically created and
destroyed; its heap address is not retained or used as the guard.

The mod reacquires the bridge through global AEA4A0, validates both vtables and
the embedded relation, rereads state/link fields and permits only that observed
closed combination. Character states 1..8 suppress as open; other combinations
are unknown and stay vanilla. The worker invalidates request/rearming on open
or unknown UI; physical and animation paths recheck it independently. No UI
memory is written. Final Release logged ui_state=2 (closed) during gameplay and
0 (unknown) at teardown. A live test proving inhibition while *otherwise eligible
native extras* would occur is still blocked by the earlier parameter guard.
This does not certify every modal, map, cutscene or concurrent UI transition.

### L3 and diagnostic bypass

No L3 request was detected from the virtual Xbox pad. During a three-second L3
pulse, bounded read-only sampling found no nonzero values in the first 128 bytes
of the consumed input-ring record. This does not prove where Steam maps L3,
that those bytes encode every button, or that a physical controller is equivalent.
No layout change, fixed controller index or additional hook was introduced.
Physical L3, game-consumed mapping and disconnect/reconnect remain unverified.

Only Debug compiles the opt-in [diagnostics] activation_seconds=3 path, requiring
diagnostics enabled, focus, current player, closed verified UI, FF/FE, run flags
and clip122. It publishes request for at most three seconds, once per process;
all physical guards, including the unchanged parameter guard, remain enforced.
Release rejects a nonzero activation_seconds and contains no development request
code. Binary string inspection confirms the request body exists only in Debug.

Two Debug game launches ended before the first hook preparation completed,
without an available exception report. The instrumented launch logged successful
MH_Initialize, but no MH_CreateHook result. Cause UNKNOWN; no bypass result is
claimed. A standalone MinHook host test passes create/enable/invoke/disable/remove
in both configurations. Release installs the game hooks and runs; this does not
explain or eliminate the Debug startup failure. No fault masking was added.

### Validation, limits and handoff

Debug and Release builds pass -Wall -Wextra -Werror. Both execute the original
config/input/extra assertions, new counter/UI classification assertions, and the
standalone MinHook test. No accepted-extra speed or animation measurement was
possible. No production lifecycle, different-FPS, collision or L3 integration
claim is made. Historical integration outlier remains UNKNOWN, not reproduced.

Game closed normally; pad reset/disconnected; only this session's ASI/INI/log
moved into ignored .cache/live-sprint-01b. Special K services remained active,
unchanged. No driver/FPS setting was changed, and fps:null is not newly verified.
EXE and loader retain their hashes above. No EXE/CPK, recovery, projection,
terrain query, vptr or heap-position writes. Detours/private pages ended with
the game process. The native DLL remains unsuitable for normal play.

Original research index SHA-256 remains ec8c6d3c459f504050d81cb7796d636176f6cc6d112ed454a31f05a2c092af3a;
feature index remains 7865e8a3018e4a8b4d02f0b420df187c6c3bf592030db6adfcf29de00161d82d.
Final seven research-tool self-checks, build-script Python compilation, both
worktrees' research TOML parses and staged/unstaged diff checks pass. New source
files also pass the explicit trailing-whitespace check.
No staging changes or commit attempts in SPRINT-01B. The previous signing failure
is preserved as history. New native files and edits remain unstaged, separate
from the existing staged INI/header/tests. No Audio or other feature work.
