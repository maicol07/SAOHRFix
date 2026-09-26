# Build identification — `sao_hr.exe`

Tutte le RVA e le signature di questo progetto sono ancorate a questa build.
Se `sha256` cambia, ogni offset va riverificato.

## Target (CONFIRMED)

| Campo | Valore |
|---|---|
| Path | `W:\SteamLibrary\steamapps\common\SAOHR\sao_hr.exe` |
| Size | 11 966 976 byte |
| SHA-256 | `1923f0d8d2cad559d6ad6e001af54ea5ea5aa70171323f42d4e1fa3d63699e43` |
| Machine | `0x8664` (x64) |
| PE TimeDateStamp | `0x59DEEE2F` = 1507800047 → 2017-10-12 09:20:47 UTC |
| ImageBase | `0x140000000` |
| EntryPoint RVA | `0x6EB140` |
| SizeOfImage | `0x10A2000` |
| Subsystem | 2 (WINDOWS_GUI) |
| DllCharacteristics | `0x8120` → HIGH_ENTROPY_VA \| DYNAMIC_BASE \| NX_COMPAT \| TERMINAL_SERVER_AWARE |
| Linker | 12.0 (MSVC 2013 → runtime MSVCR120/MSVCP120) |
| CheckSum | 0 (non calcolato) |
| PDB path | `D:\jenkins_home\workspace\pole4_multi_lang_cache_x64\Pole4\project\pole4.exe.pdb` |

**ASLR attivo** (DYNAMIC_BASE + HIGH_ENTROPY_VA): usare sempre RVA + signature scanning,
mai VA assoluti.

### Version info (risorsa, CONFIRMED)

```
CompanyName      BANDAI NAMCO Entertainment Inc.
ProductName      SWORD ART ONLINE: HOLLOW REALIZATION
FileDescription  SWORD ART ONLINE: HOLLOW REALIZATION STEAM® Version
InternalName     pole4.exe          <- codename interno del progetto: "Pole4"
OriginalFilename sao_hr.exe
FileVersion      1.0.0.0
ProductVersion   1.0.0.0
```

`FileVersion` è inutile come discriminante di build: usare SHA-256.

### Steam (CONFIRMED)

| Campo | Valore |
|---|---|
| AppID | `607890` |
| Nome | Sword Art Online: Hollow Realization Deluxe Edition |
| buildid | `2194132` |
| StateFlags | 4 (fully installed) |
| SizeOnDisk | 43 816 750 601 |
| Manifest | `W:\SteamLibrary\steamapps\appmanifest_607890.acf` |

Esiste **una sola** installazione sulla macchina. I log di terze parti in game dir
(`ReShade.log1`, `dlss5-feed.log`) citano un vecchio path
`C:\Program Files (x86)\Steam\steamapps\common\SAOHR` che **non esiste più**
(libreria spostata su `W:`). Non usarlo come riferimento.

## Sezioni PE (CONFIRMED)

| Nome | RVA | VirtualSize | RawSize | Characteristics |
|---|---|---|---|---|
| `.text` | `0x00001000` | `0x007FCF5A` | `0x007FD000` | `0x60000020` R/X |
| `.rdata` | `0x007FE000` | `0x00253A4E` | `0x00253C00` | `0x40000040` R |
| `.data` | `0x00A52000` | `0x005AC538` | `0x00078000` | `0xC0000040` RW |
| `.pdata` | `0x00FFF000` | `0x00084474` | `0x00084600` | `0x40000040` R |
| `.tls` | `0x01084000` | `0x00000099` | `0x00000200` | `0xC0000040` RW |
| `_RDATA` | `0x01085000` | `0x00000DE0` | `0x00000E00` | `0x40000040` R |
| `.rsrc` | `0x01086000` | `0x0001B2F0` | `0x0001B400` | `0x40000040` R |

Range utile per lo scanning di codice: `.text` = RVA `0x1000` … `0x7FDF5A` (~8 MB).
`.pdata` presente → unwind info completa, utile per delimitare le funzioni senza decompiler.

## Import table (CONFIRMED)

Nessun delay-import, nessun export. 14 DLL importate.

| DLL | # | Rilevanza |
|---|---|---|
| `d3d11.dll` | 2 | `D3D11CreateDevice`, `D3D11CreateDeviceAndSwapChain` |
| `dxgi.dll` | 1 | `CreateDXGIFactory` (v1, non `CreateDXGIFactory1/2`) |
| `DINPUT8.dll` | 1 | `DirectInput8Create` |
| `USER32.dll` | 45 | message loop, window, cursor, keyboard state |
| `WINMM.dll` | 3 | `timeBeginPeriod`, `timeEndPeriod`, `timeGetTime` |
| `ole32.dll` | 4 | `CoInitializeEx`, `CoCreateInstance`, `CoTaskMemFree`, `CoUninitialize` |
| `KERNEL32.dll` | 76 | file I/O, thread, **fiber**, QPC, `LoadLibraryExA`/`GetProcAddress` |
| `ADVAPI32.dll` | 6 | solo CryptoAPI (hashing) |
| `dbghelp.dll` | 9 | crash handler + `MiniDumpWriteDump` |
| `IMM32.dll` | 2 | IME per input testo |
| `SHELL32.dll` | 1 | `CommandLineToArgvW` |
| `MSVCP120.dll` / `MSVCR120.dll` | 7 / 186 | CRT MSVC 2013 |
| `steam_api64.dll` | 11 | init, callbacks, `SteamInternal_CreateInterface` |

### Assenze significative (CONFIRMED — negative evidence)

Nessun import **e nessuna stringa** che nomini queste DLL:

- `XINPUT*.dll` → **non c'è XInput**. Il supporto controller passa da DirectInput8.
- `XAUDIO2*.dll`, `dsound.dll`, `mmdevapi.dll` → nessun backend audio Microsoft diretto.
- `d3dcompiler_*.dll` → shader precompilati, nessuna compilazione a runtime.
- `d3d12.dll`, `vulkan-1.dll`, `nvapi64.dll`.
- Nessuna API overlapped/async esplicita (`GetOverlappedResult`, `CreateIoCompletionPort`) →
  I/O sincrono su thread worker (da confermare, vedi `loading.md` quando sarà scritto).

Unica stringa `.dll` non-import trovata: `!\?.dll;!\loadall.dll;.\?.dll` = `package.cpath` di Lua.

## Middleware identificato dalle stringhe (HIGH CONFIDENCE)

Versioni prese letteralmente dalle version-string embedded, non dedotte.

**Engine**: PhyreEngine (SCE). Evidenze: simboli `Phyre::P*`, classi `PMeshSegmentD3D11`,
`PDataBlockBufferD3D11`, thread `PhyreEngineRenderThread` / `PhyreEngineWorkerThread%d` /
`PhyreEngineThread` / `PhyreEngineBulletThread` / `PhyreEngineTerrainThread`,
window class `PhyreFrameworkClass` (da `dlss5-feed.log`), asset `*.fx.phyre`.
Build path: `d:\jenkins_home\workspace\pole4_multi_lang_cache_x64\phyrebase\phyrelib\...`.
**Versione PhyreEngine: UNKNOWN** — nessuna stringa di versione trovata.

**Physics**: Bullet (thread `PhyreEngineBulletThread`).

**Scripting**: Lua 5.2.1 (`$LuaVersion: Lua 5.2.1 Copyright (C) 1994-2012`), integrato via
`Phyre::PScripting` (`phyre_pscript`).

**Audio + filesystem**: CRI ADX2 / CRI File System. Tutte le librerie sono **staticamente
linkate** (build date uniforme Dec 2016), il che spiega l'assenza di import audio:

| Modulo CRI | Versione |
|---|---|
| CRI Atom / PCx64 | 2.12.01 |
| CRI AtomEx / PCx64 | 2.13.00 |
| CRI ASR (Atom Sound Renderer) | 1.04.05 |
| **CRI NcVoice WASAPI / PCx64** | **1.25.00** |
| CRI NcVoice Pseudo | 1.02.00 |
| CRI ADX Decoder | 1.00.08 |
| CRI File System | 2.74.01 |
| CRI CPK Analyzer | 0.99.54 |
| CRI Mana (video) | 2.10.00 |
| CRI Base | 2.42.07 |

→ Backend audio = **CRI ADX2 su WASAPI** (spiega l'import di `ole32!CoCreateInstance`:
`IMMDeviceEnumerator`). Dettagli in `audio.md` (blocco 4).

**Archivi**: CRI CPK. Stringhe di lookup: `pkg/data.cpk`, `pkg/%s.cpk`
(RVA `0x801A80` / `0x801A90`) → i `.cpk` di lingua sono selezionati per nome a runtime.

## Stato dell'installazione (mod di terze parti già presenti)

Non fanno parte del gioco. Rilevanti perché dimostrano cosa funziona già:

| File | Cosa dimostra |
|---|---|
| `d3d11.dll` (544 256 B, Ultimate ASI Loader x64 8.2.0, SHA-256 `bf98a529…8448`) | **L'injection via proxy `d3d11.dll` + ASI loader funziona su questo processo** |
| `SAO HR Ultrawide.asi` (55 296 B) + `Ultrawideconfig.ini` (`width=1920 height=1200`) | Esiste già una mod che patcha la risoluzione/aspect |
| `dlss5-feed.log`, `ReShade.log1` | Stack ReShade/Special K è stato caricato in passato nel processo |

⚠️ Il gioco è quindi attualmente **già moddato**. Per ogni test runtime "pulito" bisognerà
rinominare `d3d11.dll` e l'`.asi`, altrimenti le osservazioni riguardano il processo moddato.

## Come riprodurre questo documento

```powershell
cd C:\Users\Maicol\SAOHRFix
.\.venv\Scripts\python.exe tools\pe_report.py "W:\SteamLibrary\steamapps\common\SAOHR\sao_hr.exe"
.\.venv\Scripts\python.exe tools\strings_dump.py "W:\SteamLibrary\steamapps\common\SAOHR\sao_hr.exe" strings.txt
```

Toolchain di questa macchina: **niente Ghidra/IDA/radare2**. Analisi statica = `pefile` +
`capstone` nel venv locale. Vedi `docs/architecture.md`.
