# Architettura di analisi (Phase 0)

## Toolchain disponibile su questa macchina

| Strumento | Stato |
|---|---|
| Python 3.14 | presente (`C:\Users\Maicol\AppData\Local\Programs\Python\Python314`) |
| `pefile` 2024.8.26, `capstone` 5.0.7 | installati in `.venv` locale |
| Git | presente |
| Ghidra / IDA / radare2 / Binary Ninja | **assenti** |
| RenderDoc | presente (`C:\Program Files\RenderDoc`) |
| x64dbg / Cheat Engine | **assenti** (verificato 2026-09-28): necessari per i test runtime del blocco 3 |
| Compilatore C/C++ (MSVC/clang/mingw) | **assente**: nessun PoC ASI compilabile localmente |

Conseguenza: nessun recupero automatico del control flow né decompilazione. L'analisi
statica si basa su:

1. **pefile** — header, sezioni, import/export, risorse.
2. **stringhe + RVA** (`tools/strings_dump.py`) — le librerie middleware (CRI, Lua,
   PhyreEngine RTTI) sono estremamente ricche di stringhe: sono l'ancora principale.
3. **xref per scansione** — ricerca di `lea rXX, [rip+disp]` che puntano a una RVA nota,
   e di chiamate indirette alle slot IAT. Sufficiente per risalire dai messaggi di errore
   alle funzioni che li emettono.
4. **`.pdata`** — la unwind table dà l'inizio e la fine esatta di ogni funzione senza
   bisogno di un disassemblatore ricorsivo.

Tutto ciò che richiede il control flow reale (calcolo della velocità del player, matrici
di camera) resta `UNKNOWN` in analisi statica e va risolto con test runtime mirati.

## Uso del binario

Read-only. Unica eccezione: `tools/mods.ps1 off|on` rinomina (reversibile) i file delle mod di terzi.

`sao_hr.exe` ha le relocation strippate: carica sempre a `0x140000000`, quindi VA runtime = `0x140000000 + RVA`.

## Nota sull'installazione moddata

La cartella del gioco contiene già Ultimate ASI Loader (`d3d11.dll`) e
`SAO HR Ultrawide.asi`. Qualunque osservazione runtime va fatta due volte, o con l'ASI
loader disattivato, per non attribuire al gioco comportamenti introdotti da mod di terzi.

## Vincoli per Phase 1 (dai blocchi 2–3)

| Aspetto | Thread | Punto | Nota |
|---|---|---|---|
| Present / overlay draw | render thread | vtable `IDXGISwapChain::Present` | vedi `reversing/graphics.md` |
| Messaggi finestra → ImGui | main thread | `SetWindowLongPtrA(GWLP_WNDPROC)` su HWND `0xC59F08` | la WndProc del gioco non legge input |
| Blocco input di gioco con overlay aperto | main thread | latch `0x683140` (kbd), `0x687330` (mouse), `0x67EA70` (pad), `0x68FBE0` (GetKeyboardState) | già sotto mutex del gioco: nessuna race extra |
| Parametri live (es. Sprint multiplier) | scritti dalla UI (render thread), letti dal gameplay (main thread) | float atomico | niente lock nel gameplay |

Stato input ImGui: prodotto sul main thread (WndProc), consumato sul render thread → coda o double buffer
scambiato al Present.
