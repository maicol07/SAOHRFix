# Architettura di analisi (Phase 0)

## Toolchain disponibile su questa macchina

| Strumento | Stato |
|---|---|
| Python 3.14 | presente (`C:\Users\Maicol\AppData\Local\Programs\Python\Python314`) |
| `pefile` 2024.8.26, `capstone` 5.0.7 | installati in `.venv` locale |
| Git | presente |
| Ghidra / IDA / radare2 / Binary Ninja | **assenti** |
| x64dbg / Cheat Engine / RenderDoc | non verificati, presumibilmente assenti |

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

Read-only. Nessuno strumento del repository scrive su `W:\SteamLibrary\steamapps\common\SAOHR`.

## Nota sull'installazione moddata

La cartella del gioco contiene già Ultimate ASI Loader (`d3d11.dll`) e
`SAO HR Ultrawide.asi`. Qualunque osservazione runtime va fatta due volte, o con l'ASI
loader disattivato, per non attribuire al gioco comportamenti introdotti da mod di terzi.
