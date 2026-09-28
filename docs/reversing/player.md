# Player / movement

Build: `sha256 1923f0d8…9e43`. RVA relative a `0x140000000` (modulo senza relocation: VA fisso).
Classificazione evidenze: **VANILLA STATIC** salvo diversa indicazione. Nessun test runtime ancora eseguito.

## Tabella DoD blocco 3

| Elemento | RVA / struttura | Stato | Confidence |
|---|---|---|---|
| DirectInput init | `0x64F8A0`, `IDirectInput8*` @ `0xC59F18` | VANILLA STATIC | CONFIRMED |
| Keyboard device | `0x64F760` → `PInputDeviceKeyboard` (vt `0x8AD1C0`), poll `0x657840` | VANILLA STATIC | CONFIRMED |
| Mouse device | `0x64F7F0` → `PInputDeviceMouse` (vt `0x8AD188`), poll `0x657A21` | VANILLA STATIC | CONFIRMED |
| Controller device | Steam `ISteamController` (`0x683E40` init, `0x684110` poll); nessun DI/XInput | VANILLA STATIC | CONFIRMED (percorso) / PROBABLE (uso effettivo) |
| Input poll | reader thread + latch main thread `0x683140`/`0x687330`/`0x67EA70`/`0x68FBE0` in `0x696020` | VANILLA STATIC | CONFIRMED |
| Action mapping | layer fisico → pad virtuale PS (`CSysPad`, key config) | VANILLA STATIC | PROBABLE (struttura UNKNOWN) |
| Player object | classe `CChrPc` (vt `0x80AE08`, base `CChrBase`); istanza/puntatore globale | — | UNKNOWN (istanza) |
| Player position | posizione del `btKinematicCharacterController` ghost object; offset nel `CChrPc` | — | UNKNOWN |
| Player movement update | chi chiama `setWalkDirection`/`setVelocityForTimeInterval` sul KCC del player | — | UNKNOWN → `MOVEMENT-01` |
| Movement input vector | argomento di `setWalkDirection` (`[rdx]`, vec4) → KCC `+0x50` | VANILLA STATIC (lato Bullet) | HIGH (lato Bullet) / UNKNOWN (lato gioco) |
| Base/max speed | — | — | UNKNOWN → `MOVEMENT-02` |
| Movement multiplier | fattore da carico equip `move_speed_param.dat` → `stats+0x28` (`0x271436`) | VANILLA STATIC | HIGH (esistenza) / PROBABLE (effetto sulla locomozione) |
| Delta time | `0x696020`: dt da `app->vfunc[0xD8]` (base `app+0xE8`); arriva al KCC come `timeInterval` (`+0xE4`) se usato `setVelocityForTimeInterval` | VANILLA STATIC | PROBABLE |
| Combat state | classi `CChrStatusBattle`, `CFighterStatusBattle`, `CUiModeField`/`CUiModeTown` | — | UNKNOWN (flag) → `STATE-01` |
| Controllable state | — | — | UNKNOWN → `STATE-01` |
| Animation locomotion link | Phyre `PCharacterMotionGait` (`m_gaits`, `m_speedMultiplier`, `m_motionAnimSpeedScale`, `m_animSpeedLimit`) presenti; uso per il player non dimostrato | — | UNKNOWN |
| Bullet/collision integration | `CChrBase::vfunc[0x28]` → … → `PModifiedBulletKinematicCharacterController` | VANILLA STATIC | HIGH |

## Bullet / character controller (HIGH CONFIDENCE)

Catena di creazione (xref statiche):
```
CChrBase / CChrPc / CChrPartner vfunc[0x28] = 0x1EF070
  → 0x31FB90 → 0x6CAEB0 → 0x57F250 → 0x580080
    → 0x5736C0: ctor PPhysics::PInternal::PModifiedBulletKinematicCharacterController (vt 0x879BD0)
         base btKinematicCharacterController (vt 0x8C5550, ctor 0x729B20)
```
Anche `PCharacter::PPhysicsCharacterControllerComponent` (vfunc 1 → `0x7AAA60`) e `PCharacter::PUtilityCharacter`
arrivano a `0x57F250`.

Vtable `PModifiedBulletKinematicCharacterController` (`0x879BD0`):

| Slot | RVA | Ruolo (Bullet) | Evidenza |
|---|---|---|---|
| +0x08 | `0x58D340` | `updateAction(world, dt)` — **override Phyre** | slot override, non verificato oltre |
| +0x18 | `0x72A5F0` | `setWalkDirection(const btVector3&)` | scrive `+0x50` (dir), `+0x60` (normalizzata), `+0xE3 = 1` |
| +0x20 | `0x72A5A0` | `setVelocityForTimeInterval(vel, t)` | scrive `+0x50`, `+0x60`, `+0xE3 = 0`, `t` → `+0xE4` |
| +0x28..+0x58 | `0x72A4B0` … `0x729EC0` | reset/warp/preStep/playerStep/canJump/jump/onGround | ordine vtable Bullet 2.8x, non verificato singolarmente |

Nessuna chiamata diretta a `0x72A5F0`/`0x72A5A0`: solo virtuali → il chiamante lato gioco va trovato a runtime.

**Conclusione collision:** qualsiasi modifica fatta *a monte* di `setWalkDirection`/`setVelocityForTimeInterval`
(velocità desiderata) passa per il sweep di collisione del KCC. Una modifica scritta direttamente sulla
posizione la bypasserebbe.

## Modificatore di velocità esistente: `move_speed_param.dat`

- Tabella file-dati di sistema `0xA55160` (80 voci, `char*`), indice `0x2C` = `"move_speed_param.dat"`.
  Loader `0x1D3768` (costruisce il path con `"%s%s"`, legge via file system `0xC72D80`), buffer in
  `0xAEA4C0[idx]` → **`0xAEA620`**, size in `0xAEA720[idx]` → `0xAEA7D0`. Getter `GetSysData(idx)` = `0x1D2FC0`,
  size getter `0x1D3010`. (Utile anche per il blocco 5.)
- `0x26F840`: somma un valore per 10 slot equip (sub `0x36E0E0`); per le armi (tipo 1..0x16 o 0x23) moltiplica
  per `param[0]` (float).
- `0x271436` (chunk di `0x270E00`, calcolo statistiche derivate): confronta il totale con 6 soglie
  `param[+0x04..+0x18]` e prende il fattore `param[+0x1C + i*4]` → **`stats+0x28`** (float). Stesso blocco scrive
  `stats+0x20`, `+0x24` (totale peso), `+0x2C`.
- Interpretazione: **carico dell'equipaggiamento → fascia di velocità**. È un modificatore esistente, non la
  velocità base. Lettori di `stats+0x28`: UNKNOWN (runtime).

Da non usare come Sprint: altera una statistica derivata visibile/semantica (carico), non la modalità di locomozione.

## Stati di locomozione esistenti (solo RTTI, nessun comportamento verificato)

Player: `CChrStatusMove` (vt `0x80A848`), `CPcStatusMain` (vt `0x825900`), `CChrStatusJump`, `CChrStatusSquat`,
`CPcStatusSquat`, `CChrStatusSit`, `CChrStatusHug`, `CChrStatusBattle`. `CChrRtMove` (vt `0x815BB8`).
NPC: `CNpcStatusMove`, `CNpcStatusChase`, `CNpcStatusStep`, `CNpcStatusAvoid`, `CNpcStatusNavi`,
`CChrUnitRunner`, `CChrUnitChaser`. Esistenza di walk/run separati per il player: UNKNOWN.

## Raccomandazione Sprint (provvisoria)

Non ancora decidibile: manca la funzione che produce la velocità desiderata (`MOVEMENT-01`). Stato delle opzioni:

| Opzione | Valutazione attuale |
|---|---|
| A. max/desired speed | **Candidata preferita**, a monte del KCC → collisione intatta, non tocca NPC/animazioni globali/timer. Serve `MOVEMENT-01/02` per trovarla. Impatto animazione: da verificare (rischio scivolamento se il blend walk/run non segue la velocità). |
| B. modalità di locomozione esistente | Possibile se `MOVEMENT-02` mostra due fasce walk/run (es. magnitudine stick). Migliore per l'animazione. |
| C. multiplier sull'argomento di `setWalkDirection`/`setVelocityForTimeInterval` | **Sconsigliata come soluzione finale**: condiviso da tutti i personaggi (serve filtro per KCC del player), a valle di animazione/stato, e con `setVelocityForTimeInterval` va rispettato `timeInterval` (`+0xE4`). Utile solo come PoC di verifica. Hook stabile (signature di corpo unica). |
| D. fattore carico `stats+0x28` | Sconsigliata (vedi sopra). |
| Speedhack dt globale | Escluso dal brief. |

Combat compatibility: dipende da `STATE-01`.

## Test runtime

Prerequisiti comuni: x64dbg portable; `tools\mods.ps1 off`; SKIF: Special K disattivato; avviare da Steam e
**attaccare** il debugger al processo (evita il relaunch Steam; se CEG/anti-debug crasha all'attach, annotarlo).
VA = `0x140000000 + RVA`. Risultati → **VANILLA RUNTIME**.

### TEST ID: MOVEMENT-01

Purpose: trovare il chiamante lato gioco che imposta il movimento del KCC del player (funzione di locomozione).

Steps:
1. In campo aperto, nessun NPC vicino se possibile, personaggio fermo.
2. x64dbg: breakpoint su `0x14072A5F0` **e** `0x14072A5A0`.
3. Se scattano anche da fermo (NPC/partner): Edit breakpoint → Break condition `0`, Log text:
   `kcc={p:rcx} ret={p:[rsp]} xy={x:[rdx]}` → Continue. Lascia girare ~3 s fermo, poi ~3 s camminando in avanti.
4. Se scattano solo muovendosi: al break, annota call stack (tab Call Stack, almeno 4 righe).

Collect:
- quale dei due breakpoint scatta (`setWalkDirection` vs `setVelocityForTimeInterval`);
- valori `ret` (indirizzi di ritorno) — quelli che compaiono solo mentre cammini sono del player;
- `kcc` associato al player (costante mentre cammini);
- call stack.

Expected useful outcomes:
A. Un `ret` unico durante la camminata → RVA della funzione di locomozione; la analizzo staticamente.
B. `ret` identico per player e NPC → funzione condivisa; serve il `kcc` del player per filtrare (e si risale al `CChrPc`).

Return to me: file log di x64dbg (tab Log → copia tutto) + screenshot call stack.

### TEST ID: MOVEMENT-02

Purpose: capire dove entra la velocità e se esistono fasce walk/run.

Steps (stesso breakpoint condizionale di MOVEMENT-01, filtrato col `kcc` del player: condizione `rcx==<kcc>`):
1. Log text: `xy={x:[rdx]} zw={x:[rdx+8]} tprev={x:[rcx+0xE4]}` (ogni qword = 2 float; `tprev` = timeInterval
   del frame precedente, significativo solo per `0x14072A5A0`).
2. Registra ~2 s per ciascuna situazione: stick leggermente inclinato, stick al massimo, tastiera avanti,
   in città, in campo, con arma estratta / in combattimento.

Collect: i log, etichettati per situazione.

Expected useful outcomes:
A. Magnitudine costante per stick parziale/pieno → movimento a velocità fissa (niente fasce).
B. Due o più magnitudini discrete → esistono walk/run (opzione B possibile).
C. Magnitudine ∝ dt (varia con il frame time) → `setWalkDirection` riceve spostamento per frame.

Return to me: i log (valori hex: li converto io).

### TEST ID: STATE-01

Purpose: trovare un flag combat/non-combat e controllabile/non controllabile. Richiede Cheat Engine (o rimandabile
dopo MOVEMENT-01, quando avremo l'istanza `CChrPc` e potremo leggerne i campi da statica).

Steps (Cheat Engine, "Byte", unknown initial value):
1. In campo senza nemici: First Scan unknown.
2. Ingaggia un nemico (combattimento attivo): Next Scan "Changed value".
3. Esci dal combattimento: "Changed value". Rientra: "Changed value". Ripeti fino a < 200 risultati.
4. Durante un dialogo/cutscene, confronta con "Unchanged"/"Changed" per il flag controllabile.

Collect: indirizzi rimasti + valori nelle 3 situazioni; per ciascuno "Find out what writes to this address" (1 riga).

Return to me: lista indirizzi, valori, e le istruzioni che scrivono (indirizzo + opcode).
