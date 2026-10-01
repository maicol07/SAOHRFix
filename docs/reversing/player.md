# Player / movement

Aggiornamento 1 ottobre 2026: stato corrente in
[movement-report.md](movement-report.md). Le catture manuali e le liste di gap
qui sotto sono il baseline preservato nel commit `ddca350`; alcune lacune sono
state successivamente risolte con controller virtuale e log diagnostici reversibili.
Non interpretare le vecchie indicazioni "nessun hook"/"nessun commit" come stato corrente.

Build: `sha256 1923f0d8…9e43`. RVA relative a `0x140000000` (modulo senza relocation: VA fisso).
Classificazione evidenze: **VANILLA STATIC** salvo diversa indicazione. Prima cattura runtime
MOVEMENT-01 eseguita senza debugger; dettagli e limiti nella sezione seguente.

## MOVEMENT-01: risalita e prima cattura runtime

Build SHA-256 completa riverificata. Processo avviato da Steam dopo `mods.ps1 off`
e arresto dei due servizi Special K tramite SKIF. Moduli D3D11/DXGI caricati da
`C:\Windows\System32`; nessun modulo Special K/ReShade/ASI rilevato nella verifica.
Sole letture `OpenProcess(0x410)` / `ReadProcessMemory`, nessun attach, breakpoint,
scrittura nel processo o patch all'eseguibile. Salvataggio esistente caricato in field,
Kirito livello 18, tre partner presenti. Nessuna prova in combattimento o città.

### Relazione fra player e controller

**CONFIRMED, VANILLA RUNTIME** per questa sessione, PID `37196`:

| Oggetto | VA della sessione | Evidenza |
|---|---|---|
| `CChrPc` | `0x21390890` | vptr `0x14080AE08`, posizioni cambiano con il movimento fisico richiesto all'utente |
| ID fisico | `10` | `int32[CChrPc+0x9FCC]`; al titolo era `-1` |
| Record fisico | `0x20CB9D50` | ID nel primo dword; trovato nell'array del manager |
| Wrapper Phyre | `0x20CB9D60` | record `+0x10` |
| KCC del player | `0x80DF3CF0` | `[wrapper+0x148]`, vptr `0x140879BD0` |
| Backlink | `0x20CB9D60` | `[KCC+0xF0] == wrapper` |

Questi VA heap **non sono indirizzi persistenti**. Ricostruire la relazione a ogni
avvio/caricamento. Non basta cercare un vptr e assumere che l'oggetto sia attivo.

**CONFIRMED, VANILLA STATIC**, lookup dell'ID in `0x6CBEB0`:
`g = [image+0xB148B8]`, `manager = [g]`, `entries = [manager+0x18]`,
`count = int32[manager+0x134]`. Ogni elemento non nullo è un record il cui primo
dword è l'ID. Il getter restituisce lo **slot dell'array**, non il record.
Il tool dereferenzia lo slot prima di usare `record+0x10`.

### Catena statica verificata

```text
CChrPc vtable +0x180 = 0x1EA4E0
  vtable +0x548 -> 0x1E4BC0 -> current position +0x9DE0
  vtable +0x550 -> 0x1E4B40 -> requested position +0x9E10
  0x1EAE27 -> 0x320310(physics ID, scalar 60.0, current, requested, extra scalar)
    0x32037D -> 0x6CBEB0 -> matching physics record
    0x3203C8..0x3203CC: requested - current
    0x3204F4: record+0x104 = scalar argument
    0x320500: record+0x50 = displacement, potentially adjusted by a branch
    equivalently: wrapper+0xF4 = scalar; wrapper+0x40 = displacement

0x6CC090 -> 0x6CC13C -> 0x58CF40(wrapper, scalar, optional transform)
  0x58D2A2..0x58D2D2: KCC+0x100 = transformed displacement * wrapper+0xF4
  0x58D2E2..0x58D314: argument vector = (KCC+0x100).xyz * scalar argument
  0x58D31C: virtual slot +0x18 -> 0x72A5F0 setWalkDirection
  expected return address at Bullet entry: image+0x58D31F
```

**CONFIRMED** per istruzioni/slot/offset. **HIGH CONFIDENCE** come percorso della
locomozione osservata, perché la relazione degli oggetti e il fattore scritto
corrispondono al runtime. Stack, registri all'ingresso e thread ID **UNKNOWN**:
nessun breakpoint è stato installato. Non presentare il return address statico
come un return address catturato.

`0x1F5240` copia `+0x9DF0` in `+0x9E10`, poi chiama i virtuali `+0x178` e `+0x180`.
`0x21A580` è un altro wrapper che termina con un tail-jump a `0x1EA4E0`.
**CONFIRMED, VANILLA STATIC**: `0x1EAE70` copia current `+0x9DE0` in
`+0x9DF0` a `0x1EAF33`, poi chiama `0x1F69B0` a `0x1EAF59`.
Quest'ultima calcola target `+0x9E20` meno current, normalizza il delta e
aggiunge a `+0x9DF0` il vettore scalato dal parametro di movimento integrato
(`0x1F6EBD..0x1F6EC4`). `0x1F5240` trasferisce quindi questa posizione richiesta.
Il percorso normale ha dunque un produttore statico individuato; la selezione
runtime del percorso resta **HIGH CONFIDENCE**. Più routine scrivono la posizione,
incluse `0x21AF90`, `0x235680`, `0x219090` e `0x22B560`.

Correzione del blocco 3: `CChrPc vtable+0x28` contiene `0x1E4EB0`, un dispatcher
verso `vtable+0x308`, che nel player restituisce una costante da `0x904F9C`.
`0x1EF070`, la routine di creazione già individuata, è nello slot **+0x140**.
Non confondere offset in byte e indici di slot.

### Risultato della cattura fisica

`tools/movement_probe.py 37196 0x21390890 60 physical_forward_idle`:

- 5.745 campioni in 60,005 s, letture non atomiche, intervallo richiesto 10 ms.
- 228 campioni non nulli tra 35,885 e 38,258 s; 5.517 campioni nulli.
- Il fattore `wrapper+0xF4` vale `60.0` nei 228 campioni mobili, `0.0` negli altri.
- Magnitudine massima XYZ nel KCC `+0x50`: `0.084164735` unità per chiamata.
- Posizione iniziale `(3.926004, -0.055167, 163.291428)`;
  finale `(-9.570621, -0.213579, 155.499985)`.
- ID, wrapper, KCC e backlink invariati fra inizio e fine. Riposo successivo
  riconfermato con 96 campioni, vettore e fattore entrambi zero.

**CONFIRMED**: il controller individuato segue il movimento del player e torna a
zero dopo l'arresto. L'utente ha confermato l'uso della **tastiera**; questa cattura
non misura lo stick. Gli impulsi `Return`/`Space`/`W` di Computer Use non avevano
prodotto movimento misurabile; il mouse ha consentito titolo e caricamento.
Le catture precedenti, iniziate dopo il movimento, sono solo baseline di riposo.

### Velocità e delta time ancora da verificare

**PROBABLE**: `CChrPc+0x9F24` è un parametro di movimento. Getter `0x1E4EE0`;
setter `0x1E9980` riceve un vettore in RDX, lo salva a `+0x9E20` e salva XMM2 a
`+0x9F24`, XMM3 a `+0x9F2C`. Slot CChrPc/CChrBase `+0x3E8`;
setter alternativo `0x1E9A90` nello slot `+0x3F0`.
Il wrapper `0x231BB0` appartiene a CChrPartner, slot `+0x3E8`, e raggiunge
il setter con un tail-jump. Non attribuirlo a uno slot oltre il termine della
vtable CChrPc (primo elemento non-code a `+0x990`).
Non chiamarlo ancora base/max speed. `0x1F69B0` e molte altre routine lo modificano.
`0x1E2640` moltiplica questo campo per un valore letto da `0x274220()+0xE0`.

**CONFIRMED, VANILLA STATIC**: `0x208FD0` calcola un parametro di velocità
partendo da `CChrPc+0x9F20`. Applica `+0x9F88` in un ramo e moltiplicatori
da `0x274220()` secondo virtuale `+0x648` e byte `+0xF8A6` / `+0xF8AD`;
passa poi da `0x1BAF30` e limita il risultato con una costante.
Non assegnare ancora nomi combat/gait a questi flag.
`0x205BC0` chiama questo getter e scrive `+0x9F24` a `0x206107`,
`0x2064D9` e `0x20652D`; a `0x206369` passa il parametro al virtuale
`+0x3E8` insieme alla posizione target. Il getter `0x274220` restituisce
l'indirizzo della tabella `image+0xAEAB70`.
Init `0x1FE6D0`, istruzioni `0x1FE9FB..0x1FEA03`: tabella `+0x28` →
campo `+0x9F20`. Runtime tabella: `+0x28 == 0.043`, `+0x30 == 3.9`,
`+0x34 == 3.9`, `+0x38 == 1.38`. La corrispondenza con la coppia di valori
osservati 0.043/0.1677 è **HIGH CONFIDENCE**; verifica dei flag in movimento
ancora da completare.

In `0x1F69B0`, il getter `0x69B4C0` viene chiamato a `0x1F6ADF` e il risultato
moltiplicato per `CChrPc+0x9FE8` a `0x1F6AE7`. Il parametro `+0x9F24` viene
integrato con `+0x9F2C` e questo step prima di scalare il delta normalizzato.
`0x69B4C0` restituisce `[0xA63240]`, oppure `[0xA63248] * 60.0` se
`byte[0xC82FAC] == 1`. Lettura runtime in riposo: rispettivamente circa
`0.529896`, `1.0`, `0`; `CChrPc+0x9FE8 == 1.0`.
**CONFIRMED, VANILLA STATIC**: writer `0x69B430`, chiamato a `0x696143`
dall'update principale. Riceve XMM0 dopo `cvtsd2ss` del valore restituito dal
virtuale app `+0xD8`; salva il valore a `0xA63238` e il reciproco a `0xA6323C`
(fallback `60.0` per zero). Scrive `0xA63240` come clamp del valore moltiplicato
per `60.0`, fra minimo `[0xC82FA8]` e massimo `[0xA63244]`.
Lettura runtime: input circa `0.0096343`, reciproco `103.7958`, minimo `0`,
massimo `60`, step `0.578058`. **HIGH CONFIDENCE**: input in secondi e step
in unità di frame a 60 Hz. Comportamento sotto diversi framerate **UNKNOWN**.
Non moltiplicare nuovamente questo step per il dt in secondi.

**CONFIRMED**: `0x1EAE11` legge `60.0` da RVA `0xA554E4`. Questo scalar entra in
`0x320310`; a valle esiste un secondo prodotto per lo scalar di `0x58CF40`.
**CONFIRMED, static**: `0x6CBD80` legge lo scalar `1/60` da `0x81FD40`,
poi chiama `0x6CC090` a `0x6CBDA0`. Correzione del precedente indirizzo
`0x820D40`, calcolato erroneamente. Il nuovo trace del KCC conferma il caller
`0x58D31F` e il return del wrapper `0x6CC141`; dettagli nel report aggiornato.

MOVEMENT-01 ha identificato oggetti e catena candidata; resta aperta la verifica
del caller effettivo. MOVEMENT-02 non è chiuso: le quattro prove manuali sono
riportate sotto, ma asse reale, deadzone, soglie walk/run, confronto del dt a
framerate diversi e differenze città/field/combat non sono stati misurati.
Letture dei rapporti `|walk|/|KCC+0x100|` e `|KCC+0x100|/|wrapper+0x40|` sono
disponibili nel probe, ma non sostituiscono una cattura sincronizzata dei parametri.

### MOVEMENT-02: prove analogiche valide

Dopo ulteriore riavvio tramite "Gioca" dalla libreria Steam, l'utente conferma
che il pad risponde. Catture precedenti con pad non operativo escluse.
Nuova sessione: PID `62148`, CChrPc `0x21458890`, ID `10`, wrapper `0x20D81D60`,
KCC `0x80DF3CF0`; vptr e backlink verificati. Percentuali approssimate manualmente,
non misurate sull'asse di input; restano da ricostruire deadzone e soglie precise.

| Stick richiesto | Osservazione utente | Campioni mobili | Mediana KCC XYZ | Mediana KCC XZ | Mediana pc+9F24 |
|---|---|---|---|---|---|
| circa 25% | cammina | 294 / 5742 | 0.02150515 | 0.02148751 | 0.04300000 |
| circa 50% | gait incerto | 929 / 5740 | 0.02199477 | 0.02197591 | 0.04300000 |
| circa 75% | corre | 618 / 5746 | 0.02482157 | 0.02446686 | 0.04300000 |
| 100% | corre | 345 / 5728 | 0.08078582 | 0.08061422 | 0.16770001 |

25%: 60.0074 s totali, movimento rilevato fra 30.3916 e 34.7757 s.
Posizione `(36.688747, 0.425074, 178.599976)` →
`(30.100225, 0.398114, 174.825241)`. Fattore wrapper `60.0` nei 294 campioni
mobili, zero negli altri. Rapporto mediano `|walk|/|KCC+0x100| = 0.01666666719`.
**CONFIRMED, VANILLA RUNTIME** per valori/catena; **USER OBSERVATION** per gait.
Le mediane dei vettori non sono velocità in unità/secondo: campionamento a 10 ms,
letture non atomiche e dt variabile; non dedurre linearità da una sola percentuale.

50%: 60.0010 s totali, movimento fra 34.9278 e 45.4557 s, più lungo dei 3 s
richiesti. Posizione `(30.100225, 0.398114, 174.825241)` →
`(-11.016597, -0.119314, 184.975510)`. Mediana pc+9F24 identica alla prova 25%;
**PROBABLE** plateau di camminata, percentuali reali e stabilità dell'input
**UNKNOWN**. Picchi/range dei rapporti risentono delle letture non atomiche:
massimo XYZ `0.25625445`, rapporto walk/velocity `0.01610..0.01988`.
Non stimare la velocità stabile dividendo l'intero spostamento per 3 s.

75%: 60.0048 s totali, movimento fra 49.6358 e 56.0976 s.
Posizione `(-11.016597, -0.119314, 184.975510)` →
`(13.345637, -0.213579, 178.954956)`. Mediana pc+9F24 ancora `0.043`,
pur con corsa osservata dall'utente: possibile transizione o input non stabile,
non una prova di velocità costante di corsa. Soglia walk/run **UNKNOWN**.

100%: 60.0027 s totali, movimento fra 19.6783 e 25.2399 s.
Posizione `(13.345637, -0.213579, 178.954956)` →
`(40.724037, 0.156936, 185.247192)`. Mediana pc+9F24 `0.16770001`, circa
`3.9` volte `0.043`; mediana vettore XZ circa `3.75` volte quella al 25%.
Rapporto mediano walk/velocity `0.01666666807`. **CONFIRMED**: valori distinti
del parametro fra bassa deflessione e fondo corsa. **PROBABLE**: scelta di gait
con parametro discreto; curva completa magnitude/speed, deadzone, soglia e
rapporto animazione/velocità restano **UNKNOWN**.

### Valutazione Sprint attuale

| Candidate | Description | Player-only | Animation-safe | Collision-safe | Combat-safe | Recommended |
|---|---|---|---|---|---|---|
| A | risultato getter velocità `0x208FD0` prima della scrittura `+0x9F24` | filtro CChrPc/KCC verificabile | UNKNOWN | HIGH CONFIDENCE se resta nella pipeline | UNKNOWN | prima candidata per PoC, non definitiva |
| B | modalità walk/run esistente | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | solo dopo evidenza runtime |
| C | multiplier argomento Bullet | filtro KCC CONFIRMED | UNKNOWN | HIGH CONFIDENCE, sweep conservato | UNKNOWN | solo PoC, dt ancora aperto |
| D | requested position delta / parametro +0x9F24 | filtro player possibile | UNKNOWN | HIGH CONFIDENCE se passa dal KCC | UNKNOWN | pista di ricerca, nessuna patch |

Rapporto animazione/movimento **UNKNOWN**. Nessun hook Sprint consigliato come
definitivo; Phase 1 Sprint non pronta. Audio, INPUT-01 e STATE-01 non iniziati.

### Recommended Sprint hook

**HIGH CONFIDENCE, candidato di ricerca**: risultato di `0x208FD0`, o suo consumo
player in `0x205BC0`, prima della scrittura `+0x9F24`. Un eventuale PoC deve
filtrare l'istanza attiva CChrPc tramite la relazione fisica verificata, preservare
lo step temporale e lasciare la posizione richiesta passare dal KCC. Preferire
questo punto al moltiplicatore Bullet evita di scegliere un fattore temporale
come se fosse velocità. Non moltiplicare la posizione finale o gli NPC.
Il getter include modificatori di stato/statistiche: non alterarne la tabella
globale. Non è dimostrato che cambiarne il risultato aggiorni anche il gait.
Nessun hook o moltiplicatore è stato implementato.

### Remaining unknowns / Phase 1 Sprint readiness

- Stack/thread del caller effettivo: non catturati; chain statica HIGH CONFIDENCE.
- Percentuale reale dello stick, deadzone e soglia walk/run: non misurate.
- 75% con gait corsa ma mediana da camminata: richiede cattura stabile e asse reale.
- Flag `F8A6`/`F8AD` durante camminata e corsa: la verifica aggiuntiva di 60 s
  ha prodotto zero campioni mobili, quindi non li convalida.
- Dt dell'integrazione gameplay ricostruito; timestep passato al wrapper e
  collision step da confrontare sotto framerate diversi.
- Legame tra animazione e velocità, field/città/combat: da verificare.

**Phase 1 Sprint readiness: NOT READY**. Controller e parametri sono individuati;
la DoD completa di MOVEMENT-01/02 resta aperta sui punti sopra.

### Git commit / validation

Nessun commit creato: modifiche lasciate nel working tree per revisione, secondo
le istruzioni AGENTS più recenti. Nessuna modifica a executable, CPK o salvataggi
tramite strumenti di scrittura. Verifica sintassi Python, parsing TOML,
`runtime_read.py self-check`, smoke runtime e unicità delle nuove firme eseguiti.
Le firme sono build-local; i VA heap riportati sono solo evidenze della sessione.

## Tabella DoD blocco 3

| Elemento | RVA / struttura | Stato | Confidence |
|---|---|---|---|
| DirectInput init | `0x64F8A0`, `IDirectInput8*` @ `0xC59F18` | VANILLA STATIC | CONFIRMED |
| Keyboard device | `0x64F760` → `PInputDeviceKeyboard` (vt `0x8AD1C0`), poll `0x657840` | VANILLA STATIC | CONFIRMED |
| Mouse device | `0x64F7F0` → `PInputDeviceMouse` (vt `0x8AD188`), poll `0x657A21` | VANILLA STATIC | CONFIRMED |
| Controller device | Steam `ISteamController` (`0x683E40` init, `0x684110` poll); nessun DI/XInput | VANILLA STATIC | CONFIRMED (percorso) / PROBABLE (uso effettivo) |
| Input poll | reader thread + latch main thread `0x683140`/`0x687330`/`0x67EA70`/`0x68FBE0` in `0x696020` | VANILLA STATIC | CONFIRMED |
| Action mapping | layer fisico → pad virtuale PS (`CSysPad`, key config) | VANILLA STATIC | PROBABLE (struttura UNKNOWN) |
| Player object | classe `CChrPc` (vt `0x80AE08`); istanza e relazione KCC nella cattura sopra | VANILLA RUNTIME | CONFIRMED (sessione) / UNKNOWN (globale player) |
| Player position | posizione del `btKinematicCharacterController` ghost object; offset nel `CChrPc` | — | UNKNOWN |
| Player movement update | catena candidata `0x1EA4E0 → 0x320310 → wrapper → 0x58CF40 → 0x72A5F0` | VANILLA STATIC + letture runtime | HIGH CONFIDENCE; stack effettivo UNKNOWN |
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
CChrPc vtable[+0x140] = 0x1EF070
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

Nessuna chiamata diretta a `0x72A5F0`/`0x72A5A0`. Chiamante virtuale candidato
di `setWalkDirection`: `0x58D31C`; associazione oggetti runtime verificata sopra.

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
   `kcc={p:rcx} ret={p:[rsp]} xy={x:[rdx]}` → Continue. Limitare la raccolta, poi filtrare
   per il KCC ricostruito tramite ID fisico. Includere XMM2 per `setVelocityForTimeInterval`.
4. Se scattano solo muovendosi: al break, annota call stack (tab Call Stack, almeno 4 righe).

Collect:
- quale dei due breakpoint scatta (`setWalkDirection` vs `setVelocityForTimeInterval`);
- valori `ret` (indirizzi di ritorno) — un chiamante può essere condiviso da player e NPC;
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
