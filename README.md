# SAOHRFix

Reverse-engineering research and an unfinished native mod prototype for
**Sword Art Online: Hollow Realization Deluxe Edition**, PC / Steam AppID `607890`.

## Project discontinued

I have finished the game and do not want to spend more time on this project.
Research and development have therefore stopped. The repository preserves the
findings, tools, experiments and unfinished implementation for anyone who wants
to continue the work. There are no planned updates or support. Fork the
repository if you would like to take it further.

**The native Sprint prototype is not a playable release.** It builds and loads,
but the latest native test applied zero Sprint extras. Do not install or enable
it for a normal play session.

## What is here

- Build identification, D3D11/render-loop analysis, input mapping and player
  locomotion research, with build-local RVAs and signatures.
- Reversible Python diagnostics for the player, animation channel and Bullet
  character controller, plus virtual-controller and frame-limiter tools.
- Controlled collision, timing and lifecycle experiments. Research concluded
  `COLLISION-SLOPE: CLOSED pragmatically` and `READY FOR SPRINT IMPLEMENTATION`
  at SLOPE-07B. This authorized implementation, not production safety.
- A Windows x64 C++ ASI prototype using vanilla-first movement followed by an
  optional capsule-preflighted XZ physical substep, with no extra gameplay dt.
- Persistent INI configuration, keyboard/XInput Hold/Toggle logic, bounded
  diagnostics, build tooling and native tests.

Start with the [movement report](docs/reversing/movement-report.md) and
[native Sprint handoff](docs/sprint-01.md). Later findings supersede earlier
decisions; historical sections retain their evidence and uncertainty.

## Where development stopped

**SPRINT-01B BLOCKED.** Physical Left Shift requests and releases Sprint, and
the native hooks run. During the current save's run, the locomotion parameter
is `0x3E2F28C8`, outside the two accepted baseline values. All 479 eligible run
calls reached that guard and stopped there. No baseline was added to conceal it.
L3 through Steam Input remains unresolved. A conservative UI guard has evidence
for menu states but has not been qualified with otherwise eligible native extras.

Accepted native extras and animation corrections both remain **zero**. Debug
and Release build and pass tests; Debug game startup also has an unexplained
failure during hook preparation. The historical integration outlier remains
`UNKNOWN, not reproduced`. Native collision behavior, timing, concurrent object
destruction, physical controller input, mod compatibility and production
lifecycle remain unverified. Audio, ImGui, VFS, DLSS and other proposed features
were not implemented.

## Repository map

| Path | Contents |
|---|---|
| `docs/reversing/` | Build, graphics, input, player and movement findings |
| `docs/sprint-01.md` | Prototype design, actual tests, blockers and cleanup |
| `docs/architecture.md` | Research method and historical toolchain |
| `docs/roadmap.md` | Historical plan and final status |
| `research/` | Build-local address and signature catalogs |
| `tools/` | Read-only inspection and authorized reversible diagnostics |
| `native/` | Experimental C++ runtime and assertion-based tests |
| `SAOHRFix.ini` | Prototype configuration, disabled by default |

## Research setup

On Windows, create a local Python environment and install the analysis packages:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pefile capstone
```

The recorded environment used Python 3.14, pefile 2024.8.26 and Capstone 5.0.7.
Tools target the verified Steam build and the game path configured in
`tools/xref.py`. Inspect paths and prerequisites before running them.

The virtual pad requires `vgamepad` and an **already installed** ViGEmBus.
The tested package version was 0.1.3. See the
[upstream project](https://github.com/yannbouteiller/vgamepad); do not implicitly
install drivers. The stdin JSON server returns the pad to neutral after each
bounded pulse and disconnects when stdin closes. Run a tool's `self-check`
before live use. Polling records are not atomic game frames.

## Native build and development installation

The build uses Zig 0.15.2 and pinned MinHook 1.3.4. It fetches MinHook source,
compiles and runs the tests, then produces an ASI plugin and default INI:

```powershell
.\.venv\Scripts\python.exe -m pip install ziglang==0.15.2
.\.venv\Scripts\python.exe tools/build_native.py --zig .venv/Lib/site-packages/ziglang/zig.exe --config Debug
.\.venv\Scripts\python.exe tools/build_native.py --zig .venv/Lib/site-packages/ziglang/zig.exe --config Release
```

Outputs are under `.cache/native/<configuration>`. No compiled plugin, game
binary or capture is distributed in this repository. For controlled development
only, the [handoff](docs/sprint-01.md) explains the verified Ultimate ASI Loader
path, installation/removal, logs and configuration. Do not overwrite an existing
`d3d11.dll`, Ultrawide ASI or Special K installation.

The shipped configuration has `enabled=false`. Development activation uses
`enabled=true`, `mode=hold` or `mode=toggle`, `factor=1.25`, Left Shift and
XInput LeftThumb. Other factors are unsupported. This describes the implemented
request logic, not working L3 Sprint or a verified playable build. Restart after
configuration changes. Close the game before disabling or removing the plugin;
hot unloading is unsupported. Collect `SAOHRFix.log` with the matching INI when
investigating a development run.

## Research boundaries

Never permanently patch `sao_hr.exe`, edit CPK archives or redistribute game
files. Runtime instrumentation must preserve original calls and restore state.
Addresses are RVAs plus verified build-local signatures; heap addresses in the
reports apply only to their recorded sessions. Findings are labeled
`CONFIRMED`, `HIGH CONFIDENCE`, `PROBABLE` or `UNKNOWN`.

The supported EXE SHA-256 is
`1923f0d8d2cad559d6ad6e001af54ea5ea5aa70171323f42d4e1fa3d63699e43`.
Unknown builds must fall back to vanilla behavior.
