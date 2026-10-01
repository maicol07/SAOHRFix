# SAOHRFix

PC/Steam Hollow Realization reverse engineering, Phase 0. Python 3.14 in `.venv`,
pefile/Capstone, PowerShell tools. Existing Git history and `docs/reversing/` are
the technical baseline. Use RVAs plus verified build-local signatures.

- Stay on the current branch. Commit only with explicit user authorization.
- Read the applicable existing tools/docs before adding code; keep diffs scoped.
- Never patch `sao_hr.exe` permanently, edit CPK archives, or commit proprietary
  bytes, executables, large captures, downloaded binaries or process dumps.
- Label evidence CONFIRMED / HIGH CONFIDENCE / PROBABLE / UNKNOWN and distinguish
  static analysis from runtime observations. Heap addresses are session-only.
- Runtime vanilla: reversibly disable local mods with `tools/mods.ps1`, stop
  global injection via SKIF, launch via Steam. Preserve and restore prior state.
- Prefer read-only process inspection. No automatic invasive anti-debug bypass.
- Current task is MOVEMENT-01/02. No Audio, Sprint implementation, INPUT-01 or
  STATE-01 until the movement prerequisites are satisfied.

Current findings are in `docs/reversing/movement-report.md` and `player.md`.
Virtual Xbox input works through Steam with the existing ViGEmBus; use
`virtual_pad.py` rather than asking for imprecise physical stick positions.
Its percentages are not the internal axis values: measure consumed input.
`analog_probe.py` polls bounded read intervals, never atomic frames.
`walk_trace.py` is explicitly authorized temporary diagnostic instrumentation:
player/KCC/animation-channel instance vtables only, original calls preserved,
restoration required. `run_perturb.py` is an authorized diagnostic only;
live-tested at 1.10/1.25, with exact baseline bits 3E2BB98D (not float32(0.1677)).
`fps_limit.py` temporarily changes an existing NVIDIA app profile,
restores its original setting on exit, and requires game restart for cap changes.
Its sequential records and cross-thread production copies are not atomic frames.
Speed threshold and physical submission callers are identified. Actual movement
at externally observed 30/120 FPS is consistent; cap 60 lacks external FPS
verification. Animation is Case B: run downstream rate stays 1 with faster
movement. A 1.25 wall test produced a large vertical excursion absent from a
nearby vanilla comparison; matched geometry/trajectory remains unverified.
Stop perturbations until that collision is isolated. Playback calibration,
tight turns, slopes/stairs and town/combat remain gaps. Sprint is NOT READY.
Runtime clamps are 0/60; actual world position is Bullet ghost+40. Downstream
animation rate getter 6C6C80 -> 2888CC -> channel+1D0 -> 56E530 identified.
Run each new tool's `self-check` before live use; never install drivers implicitly.
