# Research architecture, Phase 0

This is the historical research method. The project is discontinued. The later
native toolchain and unfinished Sprint implementation are documented in
[sprint-01.md](sprint-01.md); they supersede the early compiler availability below.

## Toolchain available during initial reconnaissance

| Tool | Recorded status |
|---|---|
| Python 3.14 | Available locally |
| pefile 2024.8.26, Capstone 5.0.7 | Installed in the project `.venv` |
| Git | Available |
| Ghidra / IDA / radare2 / Binary Ninja | Unavailable |
| RenderDoc | Available |
| x64dbg / Cheat Engine | Unavailable as checked on 2026-09-28; originally proposed for Block 3 runtime tests |
| C/C++ compiler, MSVC/clang/mingw | Unavailable initially; Zig 0.15.2 was later added for SPRINT-01 |

Initial analysis had no automatic control-flow recovery or decompilation. It used:

1. **pefile** for headers, sections, imports/exports and resources.
2. **Strings and RVAs**, via `tools/strings_dump.py`. CRI, Lua and PhyreEngine
   RTTI provide many strings that anchor the investigation.
3. **Scanning cross-references** to RIP-relative instructions and IAT calls,
   following error strings back to their emitting functions.
4. **`.pdata`** unwind ranges for function boundaries without recursive
   disassembly. Chained entries and split functions require separate care.

Questions requiring actual control flow, such as player speed calculation and
camera matrices, remain UNKNOWN until supported by targeted analysis/runtime tests.

## Binary access

Inspection is read-only. `tools/mods.ps1 off|on` reversibly renames existing
third-party mod files. Later explicitly authorized diagnostics temporarily
instrument player/KCC/animation instances; their restoration requirements and
limits are recorded with each experiment. The native preview is a separate,
unfinished implementation, not a production version of those shims.

`sao_hr.exe` has stripped relocations and loads at `0x140000000`, so runtime
VA = `0x140000000 + RVA` for this verified build.

## Modded installation

The research installation already contained Ultimate ASI Loader, `d3d11.dll`,
and `SAO HR Ultrawide.asi`. Runtime comparisons must distinguish vanilla game
behavior from third-party injection. Preserve and restore the user's mod state.

## Historical Phase 1 constraints from Blocks 2 and 3

These were design notes, not implemented features or a current work plan.

| Concern | Thread | Candidate point | Note |
|---|---|---|---|
| Present / overlay drawing | Render thread | `IDXGISwapChain::Present` vtable | See `reversing/graphics.md` |
| Window messages to ImGui | Main thread | `SetWindowLongPtrA(GWLP_WNDPROC)`, HWND global `0xC59F08` | The game WndProc does not read gameplay input |
| Suppress game input while overlay is open | Main thread | Latches `0x683140` keyboard, `0x687330` mouse, `0x67EA70` pad, `0x68FBE0` GetKeyboardState | Already protected by game mutexes |
| Live parameters, such as a future Sprint multiplier | UI writes on render thread, gameplay reads on main thread | Atomic value | Originally proposed to avoid gameplay locks; not a validated production design |

A future ImGui input queue would be produced on the main thread by WndProc and
consumed on the render thread, using a queue or double buffer exchanged at Present.
No ImGui implementation was completed.
