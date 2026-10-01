# SAOHRFix

Progetto di modding/remaster per **Sword Art Online: Hollow Realization Deluxe Edition**
(PC / Steam AppID `607890`).

**Stato attuale: Phase 0 — Initial Reverse Engineering & Technical Reconnaissance.**
Analisi statica e prime letture runtime del movimento; nessuna patch o hook.

## Regole del progetto

- Non si modifica permanentemente `sao_hr.exe`, non si tocca `pkg/*.cpk`, non si
  ridistribuisce nessun file del gioco.
- Ogni scoperta è marcata `CONFIRMED` / `HIGH CONFIDENCE` / `PROBABLE` / `UNKNOWN`.
- Indirizzi sempre come **RVA** + signature, mai VA assoluti (oggi l'exe carica sempre a `0x140000000` perché senza relocation, ma le RVA+signature servono alla portabilità fra build).
- Ogni offset è valido solo per la build in `docs/reversing/build.md`.

## Struttura

```
docs/
  architecture.md          toolchain e metodo di analisi
  roadmap.md               fasi del progetto
  reversing/
    build.md               identificazione build + import table   [blocco 1, fatto]
    graphics.md            D3D11/DXGI/render thread/Present/WndProc [blocco 2, fatto]
    rendering.md           fatti render + mappa call site D3D11
    notes.md               piste aperte / smentite
research/                  signature e indirizzi (vuoto finché non verificati)
tools/
  pe_report.py             dump header/sezioni/import
  strings_dump.py          estrazione stringhe con RVA
  xref.py                  xref IAT/RIP/call, disasm annotato (.pdata)
  vcall_scan.py            call COM via vtable su campo noto
  sig.py                   genera/verifica AOB
  mods.ps1                 disattiva/riattiva mod di terzi (test VANILLA)
  rtti.py                  classe RTTI -> vtable (e viceversa)
  runtime_read.py          letture processo e ricerca vptr, senza debugger
  movement_probe.py        relazione player/KCC e statistiche di movimento
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pefile capstone
```

## Facts rapidi

| | |
|---|---|
| Engine | PhyreEngine (SCE), codename interno `Pole4` |
| Renderer | Direct3D 11, DXGI 1.0 |
| Scripting | Lua 5.2.1 |
| Physics | Bullet |
| Audio | CRI ADX2 (ASR), output WASAPI con fallback "Pseudo" (muto) |
| Archivi | CRI CPK (`pkg/data.cpk`, `pkg/<lang>.cpk`) |
| Input | DirectInput8 (solo kbd/mouse) + polling USER32 + Steam `ISteamController` per il pad (**niente XInput, niente Raw Input**) |
| Physics player | Bullet `btKinematicCharacterController` (wrapper Phyre) |
