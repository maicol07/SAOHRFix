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

Current findings and test gaps are in `docs/reversing/player.md`: player KCC
relationship and movement/riposo capture confirmed; caller stack/thread,
framerate scenarios, exact analog magnitude/deadzone/threshold, gait/animation
and combat/city differences remain unverified. `runtime_read.py self-check` checks scan alignment and the
Windows memory-region layout; `movement_probe.py` provides a read-only smoke
capture. Physical input is required for labeled stick tests.
