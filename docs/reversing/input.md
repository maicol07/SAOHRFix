# Input

Build: `sha256 1923f0d8…9e43`. RVA relative a `0x140000000`. Salvo diversa indicazione: **VANILLA STATIC**.
MOVEMENT-01 runtime: caricamento raggiunto tramite mouse con Computer Use; gli impulsi
di tastiera sintetici provati non hanno prodotto movimento misurabile. Movimento fisico
dell'utente confermato tramite KCC/posizione e classificato dall'utente come tastiera;
backend pad e percentuale stick ancora **UNKNOWN**. Prime prove analogiche invalide:
il pad non rispondeva via Steam Input; hot plugging non verificato.
Verifica UI successiva: Steam Input attivo, controller PlayStation riconosciuto,
layout ufficiale AQURIA, stick sinistro assegnato a "Muovi". Processo con
`steam_api64.dll`, `steamclient64.dll`, `gameoverlayrenderer64.dll` caricati.
Avvio iniziale via `steam://rungameid/607890`; ulteriore riavvio tramite pulsante
"Gioca" della libreria per separare il test del menu dalla cattura locomozione.
Questi fatti non dimostrano che il backend pad del gioco riceva dati validi.
L'utente ha poi confermato che il pad funziona dopo l'avvio dal pulsante "Gioca".
**CONFIRMED, USER OBSERVATION**; causa del precedente mancato input **UNKNOWN**.
Non attribuire la differenza al protocollo di avvio o all'hot plugging senza
un confronto controllato.
Questo non chiude INPUT-01 e non prova l'uso effettivo di Steam `ISteamController`.
Nota: il modulo ha le relocation strippate → carica sempre a `0x140000000` (VA = `0x140000000 + RVA`), utile per i test runtime.

## Pipeline ricostruita

```
DirectInput8 (keyboard, mouse)          Steam Input / ISteamController (gamepad)       USER32 GetKeyboardState / GetKeyState
      │                                          │                                            │
reader thread "KbRead" / "MouseRead"      reader thread "PadRead"                         (key config / text input?)
      │ (MicroThread, stato protetto da mutex)   │                                            │
      ▼                                          ▼                                            ▼
main thread, app "animate" 0x696020:  0x683140 (kbd)  0x687330 (mouse)  0x67EA70 (pad)  0x68FBE0 (GetKeyboardState)
      │  ognuno: WaitForSingleObject(mutex) → latch/update → ReleaseMutex
      ▼
stato "pad virtuale" di gioco (layout PlayStation: Cross/Circle/Square/Triangle/StartOption/SelectShare/TouchPad/…)
      ▼
gameplay (0x165A10 = update gioco, chiamato subito dopo, da 0x696020)
```

Il gioco è un port PS4/Vita: il gameplay ragiona su un pad virtuale stile PlayStation (`CSysPad`), la tastiera
arriva su quel pad tramite key config (`CUiKeyConfigWin32`, `CKeyConfigWin32Proc`, `key_config*.dat`).

## DirectInput

| Elemento | RVA / valore | Confidence |
|---|---|---|
| `DirectInput8Create` | `0x64F8A0` @ `0x64F8CB` (thunk `0x6EA76C`), chiamato dall'init app `0x6550A0` | CONFIRMED |
| `IDirectInput8*` | globale **`0xC59F18`** | CONFIRMED |
| Enumerazione | `EnumDevices(DI8DEVCLASS_ALL, cb=0x64E250, NULL, DIEDFL_ATTACHEDONLY)` | CONFIRMED |
| Callback | `dwDevType & 0xFF`: `0x13` keyboard → `0x64F760`; `0x12` mouse → `0x64F7F0`; **qualsiasi altro tipo ignorato** | CONFIRMED |
| Keyboard | `CreateDevice` → `SetDataFormat(0x8C22F8 = c_dfDIKeyboard, 256 B)` → `SetCooperativeLevel(HWND, 6 = NONEXCLUSIVE\|FOREGROUND)` → `Acquire` → wrapper `PFramework::PInputDeviceKeyboard` (0x150 B, ctor `0x64A870`, vtable `0x8AD1C0`) | CONFIRMED |
| Mouse | come sopra, `SetDataFormat(0x8C22D8 = c_dfDIMouse2: 20 B, 11 oggetti)`, coop 6 → wrapper `PFramework::PInputDeviceMouse` (0x200 B, ctor `0x64A910`, vtable `0x8AD188`) | CONFIRMED |
| Joystick/gamepad DirectInput | **nessuno** (filtrato dalla callback) | CONFIRMED |
| Poll keyboard | `PInputDeviceKeyboard::vfunc[5]` = **`0x657840`**: `GetDeviceState(256)`; su errore azzera stato e ri-`Acquire` finché `DIERR_INPUTLOST`; su successo mappa 96 key-code engine tramite tabella DIK `0xA625C0` in `this+0xF0` (held), poi `0x6577A0` (edge: probabilmente `+0x30`/`+0x90` pressed/released) | CONFIRMED (poll) / PROBABLE (semantica dei 3 array da 0x60 B) |
| Poll mouse | `0x657A21` (chunk di `PInputDeviceMouse`): `GetCursorPos` + `GetWindowRect` + `GetClientRect` + `GetWindowInfo` + `ScreenToClient`; posizione assoluta client ×255 in `+0x1F0/+0x1F4`, `+0x1F8`; pulsanti (bit 7 di `rgbButtons`) in `+0x1FC..+0x1FE` | CONFIRMED |
| `Unacquire` / `GetDeviceData` (buffered) | non trovati nel percorso di poll: solo stato immediato | PROBABLE |

## Controller: Steam Input (ISteamController)

- Nessun XInput, nessun HID, nessun joystick DirectInput → l'unico percorso gamepad nel binario è **Steamworks
  `ISteamController`** (`"SteamController005"`, classe `PFramework::PInputDevicePadSteamController`,
  test `CSteamControllerTest`). CONFIRMED (per esclusione + stringhe/RTTI).
- Init `0x683E40`: `GetActionSetHandle("ship_controls"/"menu_controls")`, `GetDigitalActionHandle(turn_left,
  turn_right, forward_thrust, backward_thrust, fire_lasers, pause_menu, menu_up/down/left/right/select/cancel)`,
  `GetAnalogActionHandle("analog_controls")`. Offset vtable `+0x28/+0x40/+0x58` coerenti con `SteamController005`.
- Poll `0x684110` (+ chunk `0x684181`): `ActivateActionSet` (`+0x30`), 5× `0x684540` (digital action data),
  log `"Controller (%d) has been disconnected."`.
- ⚠️ **Questi sono i nomi del sample Valve "SpaceWar"/SteamworksExample.** Due possibilità, non distinguibili
  staticamente: (a) il gioco pubblica davvero un action manifest con quei nomi riutilizzati; (b) è codice di
  esempio mai usato e il gamepad arriva da un altro percorso. → **PROBABLE**, test `INPUT-01`.
- Thread `"PadRead"` + mutex `"PadMutex"` (`0xC69070`) creati da `0x67E870`; latch sul main thread `0x67EA70`
  (→ `0x67D640`, `0x67E4C0`).
- Deadzone, rappresentazione interna di stick/trigger/L3/R3: **UNKNOWN**. Con Steam Input, L3/R3 e deadzone sono
  in gran parte configurati lato Steam; il gioco vede action, non tasti fisici.

Conseguenza per Sprint su gamepad: un bind "L3" non si intercetta con API Windows; va letto dallo stato pad
virtuale del gioco (dopo il latch) oppure aggiunto come action Steam. Da decidere dopo `INPUT-01`.

## USER32 polling aggiuntivo

| API | Sito | Note |
|---|---|---|
| `GetKeyboardState` | `0x68EE20` @ `0x68F3AC` (sotto mutex `0xC6BF80`, chiamato da `0x68FBE0` ogni frame) e `0x6903B0` @ `0x6904A7` | percorso tastiera **indipendente** da DirectInput (key config / testo?) — scopo PROBABLE |
| `GetKeyState` | `0x6828F0` @ `0x68294B` | probabilmente toggle (CapsLock/NumLock) |
| `GetCursorPos` / `ScreenToClient` | `0x657A21` | posizione mouse assoluta |
| `GetAsyncKeyState` | **non importato** | CONFIRMED |
| `SetWindowsHookExA` | `0x695990` @ `0x6959E4` | tipo hook UNKNOWN (IME / tasti di sistema?) |
| Raw Input | non importato | CONFIRMED |

WndProc (`0x650440`) **non** processa tastiera/mouse (vedi `graphics.md`).

## Action mapping

- PhyreEngine fornisce `PInputs::PInputMap/PInputAction/PInputSource*` e `PFramework::PInputMapper` (RTTI presenti).
  Uso effettivo da parte del gameplay: **UNKNOWN** (possono essere solo metadati di reflection linkati).
- Layer di gioco: `CSysInputDevice` (vtable `0x8B4D48`), `CSysKeyboard` (`0x8B48A8`), `CSysPad` (`0x8B4840`),
  key config `CUiKeyConfigWin32` / `CUiKeyConfigGamepadWin32` / `CKeyConfigWin32Proc`; nomi tasti `Key_*`,
  nomi pulsanti PS (`Cross`, `Circle`, …). Conclusione: **esiste un layer di mapping fisico → pad virtuale**;
  struttura e numero di action: UNKNOWN.

## Thread

| Funzione | Thread | Confidence |
|---|---|---|
| Poll DI keyboard/mouse, poll Steam pad | reader thread dedicati (`KbRead`, `MouseRead`, `PadRead`) | HIGH (nomi + mutex) |
| Latch stato input (`0x683140`, `0x687330`, `0x67EA70`, `0x68FBE0`) | main thread, dentro `animate` `0x696020` | CONFIRMED |
| Gameplay update (`0x165A10`) | main thread, subito dopo i latch | CONFIRMED (ordine di chiamata) |

## Implicazioni per l'overlay ImGui (Phase 1)

- Punto di blocco raccomandato: i **4 latch sul main thread** (`0x683140`, `0x687330`, `0x67EA70`, `0x68FBE0`).
  Con overlay aperto: eseguire il latch originale (tiene coerenti i reader thread) e poi azzerare lo stato di gioco,
  oppure saltarlo. Da decidere dopo aver visto il layout dello stato (runtime).
- Non basta filtrare la WndProc: il gioco non legge input da lì.
- ImGui prende input dalla WndProc (main thread) e disegna sul render thread → coda/double-buffer (vedi `architecture.md`).
- Rischio race: nessuno aggiuntivo se il blocco avviene dentro il latch (già sotto mutex, già sul main thread).

## Test runtime

### TEST ID: INPUT-01

Purpose: stabilire se il percorso Steam Input (`0x684110`) è quello che fornisce davvero il gamepad.

Prerequisiti: x64dbg (portable, gratuito). `tools\mods.ps1 off`. Controller collegato.
Steam avvia il gioco normalmente; **attaccare** x64dbg al processo già avviato (evita il relaunch di
`SteamAPI_RestartAppIfNecessary`). Il gioco usa Steam CEG / `IsDebuggerPresent`: se crasha all'attach, annotarlo.

Steps:
1. Avvia il gioco, arriva al controllo del personaggio.
2. x64dbg → Attach `sao_hr.exe`. Imposta breakpoint su `0x140684181` e `0x140684540`. Continua (F9).
3. Muovi lo stick sinistro e premi Cross/A.
4. Se scatta: annota lo stack (3 livelli) e rimuovi i breakpoint. Se non scatta entro ~10 s: annotalo.
5. Ripeti una volta con la **Steam Input disattivata** per il gioco (Proprietà gioco → Controller → Disattiva Steam Input) e verifica se il pad funziona ancora in gioco.

Collect:
- scatta sì/no (con Steam Input attiva);
- il pad funziona sì/no con Steam Input disattivata;
- screenshot del call stack se scatta.

Expected useful outcomes:
A. Scatta + pad morto senza Steam Input → Steam Input è l'unico percorso; Sprint su pad = action/stato pad virtuale.
B. Non scatta → esiste un altro percorso (da cercare a partire dal latch `0x67EA70`).

Return to me: le due risposte sì/no + call stack.

VANILLA RUNTIME.

## MOVEMENT-01/02: asse consumato, aggiornamento 1 ottobre 2026

**CONFIRMED, static:** `0x205BC0` ottiene l'oggetto assi tramite `0x1CE560`,
chiama `0x2D0290`/`0x2D04D0` con storico 0 e conserva gli assi signed16 in
R12D/R15D. Ring `0xC66D60`, 64 record di `0x8C`, X/Y a `+0x80/+0x82`;
conteggio `0xC69060`, cursore `0xC69068`. Con storico attivo, slot `(cursor-1)%64`;
con conteggio zero, record base. L'oggetto può invertire il segno tramite `+0x70E`.

**CONFIRMED, runtime:** Xbox virtuale ViGEm, mantenuto collegato durante l'avvio
da Steam, produce assi interni e movimento. Il gioco continua a consumare il
proprio percorso Steam; il pad virtuale non implica un nuovo percorso XInput nel gioco.
I valori software richiesti non equivalgono a percentuali dell'asse interno.

Nel ramo analogico `0x20646A`, R12D diventa X² e R15D X²+Y². Il trace del
setter `0x1E9980`, return `0x1E993F`, outer return `0x206660`, intercetta
questa magnitudine realmente consumata. Applicare l'interpretazione soltanto
a questi caller verificati. Segni degli assi persi a questo punto.

Polling ring, eventi del setter e submission KCC hanno fasi/thread differenti:
nessun record è presentato come frame atomico completo. Metodo, risultati e
limiti in [movement-report.md](movement-report.md); INPUT-01 generale non eseguito.
