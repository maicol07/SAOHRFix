# Build identification, sao_hr.exe

Every RVA and signature in this project is tied to this build. If its SHA-256
changes, revalidate every offset.

## Target, CONFIRMED

| Field | Value |
|---|---|
| Recorded path | `W:\SteamLibrary\steamapps\common\SAOHR\sao_hr.exe` |
| Size | 11,966,976 bytes |
| SHA-256 | `1923f0d8d2cad559d6ad6e001af54ea5ea5aa70171323f42d4e1fa3d63699e43` |
| Machine | `0x8664`, x64 |
| PE TimeDateStamp | `0x59DEEE2F` = 1507800047, 2017-10-12 09:20:47 UTC |
| ImageBase | `0x140000000` |
| EntryPoint RVA | `0x6EB140` |
| SizeOfImage | `0x10A2000` |
| Subsystem | 2, WINDOWS_GUI |
| DllCharacteristics | `0x8120`: HIGH_ENTROPY_VA, DYNAMIC_BASE, NX_COMPAT, TERMINAL_SERVER_AWARE |
| Linker | 12.0, MSVC 2013, MSVCR120/MSVCP120 runtime |
| CheckSum | 0, not computed |
| Embedded PDB path | `D:\jenkins_home\workspace\pole4_multi_lang_cache_x64\Pole4\project\pole4.exe.pdb` |

**ASLR is effectively inactive for the main module**, corrected during Block 3.
DYNAMIC_BASE is set, but FILE_HEADER.Characteristics is `0x23`, meaning
RELOCS_STRIPPED, EXECUTABLE_IMAGE and LARGE_ADDRESS_AWARE. The relocation
directory is empty, so the loader cannot relocate this image. It consistently
loads at `0x140000000`. Runtime VA is base plus RVA; use RVAs and signatures
for portability rather than relying on absolute addresses.

### Resource version information, CONFIRMED

```text
CompanyName      BANDAI NAMCO Entertainment Inc.
ProductName      SWORD ART ONLINE: HOLLOW REALIZATION
FileDescription  SWORD ART ONLINE: HOLLOW REALIZATION STEAM® Version
InternalName     pole4.exe
OriginalFilename sao_hr.exe
FileVersion      1.0.0.0
ProductVersion   1.0.0.0
```

The internal project codename is Pole4. FileVersion is not a useful build
discriminator; use SHA-256.

### Steam installation, CONFIRMED

| Field | Value |
|---|---|
| AppID | `607890` |
| Name | Sword Art Online: Hollow Realization Deluxe Edition |
| buildid | `2194132` |
| StateFlags | 4, fully installed |
| SizeOnDisk | 43,816,750,601 |
| Manifest | `W:\SteamLibrary\steamapps\appmanifest_607890.acf` |

Only one installation existed on the research machine. Third-party logs in the
game directory, ReShade.log1 and dlss5-feed.log, refer to an old installation
under `C:\Program Files (x86)\Steam\steamapps\common\SAOHR` that no longer
existed after the library moved to W:. Do not use those paths as current evidence.

## PE sections, CONFIRMED

| Name | RVA | VirtualSize | RawSize | Characteristics |
|---|---|---|---|---|
| `.text` | `0x00001000` | `0x007FCF5A` | `0x007FD000` | `0x60000020`, R/X |
| `.rdata` | `0x007FE000` | `0x00253A4E` | `0x00253C00` | `0x40000040`, R |
| `.data` | `0x00A52000` | `0x005AC538` | `0x00078000` | `0xC0000040`, RW |
| `.pdata` | `0x00FFF000` | `0x00084474` | `0x00084600` | `0x40000040`, R |
| `.tls` | `0x01084000` | `0x00000099` | `0x00000200` | `0xC0000040`, RW |
| `_RDATA` | `0x01085000` | `0x00000DE0` | `0x00000E00` | `0x40000040`, R |
| `.rsrc` | `0x01086000` | `0x0001B2F0` | `0x0001B400` | `0x40000040`, R |

The code-scanning range is `.text`, RVA `0x1000` through `0x7FDF5A`, roughly
8 MB. `.pdata` supplies unwind information useful for locating function ranges.

## Import table, CONFIRMED

There are no delay imports or exports. Fourteen DLLs are imported.

| DLL | Count | Relevance |
|---|---|---|
| `d3d11.dll` | 2 | D3D11CreateDevice, D3D11CreateDeviceAndSwapChain |
| `dxgi.dll` | 1 | CreateDXGIFactory v1, not CreateDXGIFactory1/2 |
| `DINPUT8.dll` | 1 | DirectInput8Create |
| `USER32.dll` | 45 | Message loop, window, cursor and keyboard state |
| `WINMM.dll` | 3 | timeBeginPeriod, timeEndPeriod, timeGetTime |
| `ole32.dll` | 4 | CoInitializeEx, CoCreateInstance, CoTaskMemFree, CoUninitialize |
| `KERNEL32.dll` | 76 | File I/O, threads, fibers, QPC, LoadLibraryExA/GetProcAddress |
| `ADVAPI32.dll` | 6 | CryptoAPI hashing only |
| `dbghelp.dll` | 9 | Crash handler and MiniDumpWriteDump |
| `IMM32.dll` | 2 | IME text input |
| `SHELL32.dll` | 1 | CommandLineToArgvW |
| `MSVCP120.dll` / `MSVCR120.dll` | 7 / 186 | MSVC 2013 CRT |
| `steam_api64.dll` | 11 | Initialization, callbacks, SteamInternal_CreateInterface |

### Significant absences, negative evidence

No import or DLL-name string was found for:

- XINPUT DLLs. The original suggestion that controllers therefore use generic
  DirectInput was rejected later. DirectInput enumeration accepts only keyboard
  and mouse; see input.md for the Steam/game-logical input path.
- XAUDIO2, dsound or mmdevapi, so no directly imported Microsoft audio backend.
- d3dcompiler: shaders are precompiled, with no observed runtime compilation.
- d3d12.dll, vulkan-1.dll or nvapi64.dll.

No explicit overlapped/asynchronous APIs such as GetOverlappedResult or
CreateIoCompletionPort were imported. Synchronous I/O on worker threads was a
hypothesis, not a completed loading analysis. The only non-import `.dll` string
found was Lua's package.cpath, `!\?.dll;!\loadall.dll;.\?.dll`.

## Middleware identified from strings, HIGH CONFIDENCE

Versions below are literal embedded version strings, not inferred releases.

**Engine:** PhyreEngine, SCE. Evidence includes Phyre::P* symbols,
PMeshSegmentD3D11, PDataBlockBufferD3D11, asset names ending `.fx.phyre`, and
threads PhyreEngineRenderThread, PhyreEngineWorkerThread%d, PhyreEngineThread,
PhyreEngineBulletThread and PhyreEngineTerrainThread. PhyreFrameworkClass was
recorded in a modded log. Build paths include
`d:\jenkins_home\workspace\pole4_multi_lang_cache_x64\phyrebase\phyrelib\...`.
The PhyreEngine version is UNKNOWN; no version string was found.

**Physics:** Bullet, including the PhyreEngineBulletThread name.

**Scripting:** Lua 5.2.1, with `$LuaVersion: Lua 5.2.1 Copyright (C) 1994-2012`,
integrated through Phyre::PScripting, phyre_pscript.

**Audio and filesystem:** CRI ADX2 / CRI File System, statically linked. Uniform
December 2016 library build dates explain the absence of imported audio DLLs.

| CRI module | Version |
|---|---|
| CRI Atom / PCx64 | 2.12.01 |
| CRI AtomEx / PCx64 | 2.13.00 |
| CRI ASR, Atom Sound Renderer | 1.04.05 |
| CRI NcVoice WASAPI / PCx64 | 1.25.00 |
| CRI NcVoice Pseudo, silent output | 1.02.00 |
| CRI ADX Decoder | 1.00.08 |
| CRI File System | 2.74.01 |
| CriFsBinder | 1.02.70 |
| CRI CPK Analyzer | 0.99.54 |
| CRI Mana, video | 2.10.00 |
| CRI Base | 2.42.07 |

The library-level audio backend is CRI ADX2 with the ASR renderer, selecting
NcVoice WASAPI or silent Pseudo output at runtime. CoCreateInstance probably
creates IMMDeviceEnumerator. The embedded warning
`W2014021962:WASAPI is not available. Atom library operates without sound output.`
shows an intentional silent fallback path. The hypothesis that a Windows device
change leaves the game on Pseudo rather than crashing is PROBABLE and was never
validated by the dedicated audio investigation, which was not started.

**Archives:** CRI CPK. Lookup strings `pkg/data.cpk` and `pkg/%s.cpk` at
`0x801A80` / `0x801A90` select language archives by name at runtime.

## Third-party mods present in the research installation

These are not game components and are not distributed here.

| File | What it establishes |
|---|---|
| d3d11.dll, 544,256 bytes, Ultimate ASI Loader x64 8.2.0, SHA-256 `bf98a529…8448` | Proxy DLL / ASI injection works in this process |
| SAO HR Ultrawide.asi, 55,296 bytes, plus Ultrawideconfig.ini, width=1920 height=1200 | A resolution/aspect mod was already installed |
| dlss5-feed.log, ReShade.log1 | ReShade/Special K had previously loaded into the process |

Vanilla research tests reversibly disabled these local mods and global injection.
Native ASI tests necessarily retained the verified loader and documented the
active third-party components separately.

## Reproduction

From the repository root, with the local environment configured:

```powershell
.\.venv\Scripts\python.exe tools\pe_report.py "W:\SteamLibrary\steamapps\common\SAOHR\sao_hr.exe"
.\.venv\Scripts\python.exe tools\strings_dump.py "W:\SteamLibrary\steamapps\common\SAOHR\sao_hr.exe" strings.txt
```

Initial static analysis used pefile and Capstone, without Ghidra/IDA/radare2.
See docs/architecture.md for the historical method.
