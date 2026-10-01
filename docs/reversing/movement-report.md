# SAOHRFix — Movement report

Data: 1 ottobre 2026. Build Steam PC, SHA-256
`1923f0d8d2cad559d6ad6e001af54ea5ea5aa70171323f42d4e1fa3d63699e43`.
Gli indirizzi di codice sono RVA, base modulo `0x140000000`.
Fonti del progetto: [player.md](player.md), [input.md](input.md),
[addresses.toml](../../research/addresses.toml),
[signatures.toml](../../research/signatures.toml).

Evidenze: **CONFIRMED** = istruzioni verificate o valori letti runtime;
**HIGH CONFIDENCE** = associazione sostenuta da più evidenze, senza trace completo;
**PROBABLE** = ipotesi da verificare; **UNKNOWN** = non dimostrato.
Le osservazioni del gait sono dichiarazioni dell'utente, non letture dello stato animazione.

## MOVEMENT-01 findings

- **CONFIRMED, runtime:** identificata la relazione fra CChrPc, ID fisico,
  wrapper Phyre e Bullet KCC. Verificata nuovamente dopo i riavvii.
- **CONFIRMED, runtime:** il vettore KCC cambia durante il movimento del player
  e torna a zero al rilascio. Prima cattura fisica classificata dall'utente come
  tastiera: 228 campioni mobili su 5.745; fattore wrapper `60.0` in movimento,
  `0.0` in riposo. Posizione iniziale e finale differenti, backlink invariato.
- **CONFIRMED, static:** individuata la chiamata virtuale a `setWalkDirection`
  in `0x58D31C`, dal wrapper `0x58CF40`.
- **HIGH CONFIDENCE:** questa catena serve la locomozione osservata. Stack,
  registri all'ingresso e thread del caller effettivo non sono stati catturati.

Metodo: letture `OpenProcess(0x410)` / `ReadProcessMemory`, senza debugger,
breakpoint o scritture nel processo. Mod locali disabilitate reversibilmente,
servizi Special K arrestati, gioco avviato da Steam. Nessuna patch applicata.

## MOVEMENT-02 findings

Quattro catture separate, circa 60 s ciascuna, polling richiesto ogni 10 ms.
Percentuali dello stick stimate manualmente; asse fisico non acquisito.
Scenario: field, Kirito livello 18, tre partner. Nessuna prova in città o combattimento.

| Stick richiesto | Gait osservato dall'utente | Campioni mobili | Mediana vettore KCC XZ | Mediana CChrPc+9F24 |
|---|---|---|---|---|
| circa 25% | cammina | 294 / 5.742 | 0.021488 | 0.043000 |
| circa 50% | incerto | 929 / 5.740 | 0.021976 | 0.043000 |
| circa 75% | corre | 618 / 5.746 | 0.024467 | 0.043000 |
| 100% | corre | 345 / 5.728 | 0.080614 | 0.167700 |

**CONFIRMED:** il parametro mediano a fondo corsa è circa `3.9×` quello delle
prime tre catture. Il rapporto mediano fra vettore walk e vettore KCC `+0x100`
è circa `1/60` nelle quattro prove.

**PROBABLE:** esiste una selezione di velocità/gait con valori distinti, anziché
una semplice proporzionalità continua alla deflessione. Non è ancora una curva
magnitude/speed ricostruita. Al 75% la corsa osservata e la mediana `0.043` non
concordano abbastanza da fissare una soglia.

Le mediane KCC sono magnitudini di vettori di spostamento, **non velocità in
unità/secondo**. Letture non atomiche, terreno e dt variabile limitano il confronto.
Gli intervalli mobili osservati non coincidono sempre con i 3 s richiesti;
non dividere lo spostamento totale per 3 s per stimare la velocità.

Le prove precedenti con pad non operativo sono escluse. Il pad ha funzionato
dopo un ulteriore avvio dal pulsante “Gioca” di Steam; causa della differenza
**UNKNOWN**, hot plugging non dimostrato.

## Player controller

**CONFIRMED:** CChrPc ha vtable RVA `0x80AE08`; il suo controller è
`PModifiedBulletKinematicCharacterController`, vtable RVA `0x879BD0`, derivato
dal Bullet `btKinematicCharacterController`, vtable RVA `0x8C5550`.

```text
CChrPc+0x9FCC → physics ID
[image+0xB148B8] → global object → manager
manager+0x18 → record pointer array; manager+0x134 → count
record first dword == physics ID
record+0x10 → wrapper
[wrapper+0x148] → KCC
[KCC+0xF0] == wrapper
```

Ultima sessione delle prove: PID `62148`, CChrPc VA `0x21458890`, ID `10`,
wrapper VA `0x20D81D60`, KCC VA `0x80DF3CF0`. Sono **VA della sessione**,
da risolvere nuovamente a ogni avvio/caricamento.

Il lookup `0x6CBEB0` restituisce lo slot dell'array, da dereferenziare.
La creazione del controller parte dallo slot CChrPc **+0x140** (`0x1EF070`),
non da `+0x28`.

## CChrPc locomotion chain

**CONFIRMED, static** per funzioni, offset e operazioni; **HIGH CONFIDENCE**
per la selezione del percorso durante le catture:

```text
0x205BC0 → 0x208FD0 → derived parameter at CChrPc+0x9F24
  virtual +0x3E8 → 0x1E9980: target at +0x9E20, parameter at +0x9F24
0x1EAE70 → 0x1F69B0: normalized target-current, integration into +0x9DF0
0x1F5240: +0x9DF0 → requested position +0x9E10
  virtual +0x180 → 0x1EA4E0 → 0x320310
    requested-current → wrapper+0x40; scale → wrapper+0xF4
0x6CC090 → 0x58CF40
  transformed displacement * wrapper scale → KCC+0x100
  KCC+0x100 * update scalar → setWalkDirection argument
0x58D31C → virtual +0x18 → 0x72A5F0 → KCC+0x50
```

Sono presenti altri writer della posizione richiesta. Questa è una catena
ricostruita, non un call stack runtime registrato. `image+0x58D31F` è il return
address atteso staticamente, non un indirizzo catturato all'ingresso di Bullet.

## Movement speed source

**CONFIRMED, static:** `0x274220` restituisce la tabella RVA `0xAEAB70`.
L'init `0x1FE6D0`, store `0x1FEA03`, copia tabella `+0x28` in CChrPc `+0x9F20`.
Il getter `0x208FD0` parte da questa base, applica moltiplicatori di stato/statistiche,
passa da `0x1BAF30` e limita il risultato. `0x205BC0` lo scrive a `+0x9F24`.

| Elemento | Valore/indirizzo | Evidenza |
|---|---|---|
| Base del parametro | CChrPc `+0x9F20` | static CONFIRMED |
| Parametro derivato | CChrPc `+0x9F24` | static/runtime CONFIRMED |
| Tabella base | `0xAEAB70+0x28 = 0.043` | runtime CONFIRMED |
| Moltiplicatori | tabella `+0x30 = 3.9`, `+0x34 = 3.9`, `+0x38 = 1.38` | runtime CONFIRMED |
| Selettori di ramo | virtuale `+0x648`, byte `+0xF8A6` e `+0xF8AD` | static CONFIRMED; significato UNKNOWN |

**HIGH CONFIDENCE:** `0.043 × 3.9 = 0.1677` spiega la coppia di valori misurata.
La lettura aggiuntiva dei flag durante il movimento ha raccolto zero campioni
mobili: non conferma quale ramo fosse attivo.
`+0x9F24` è un parametro derivato, non un “max speed” universale dimostrato.

**Delta time:** writer `0x69B430`, chiamato in `0x696143`, produce
`A63240 = clamp(app_dt × 60, minimum, maximum)`; getter `0x69B4C0` lo fornisce
all'integrazione di `0x1F69B0`, ulteriormente scalato da CChrPc `+0x9FE8`.
Runtime: input circa `0.0096343`, reciproco `103.7958`, step `0.578058`.
**HIGH CONFIDENCE:** input in secondi, step in unità di frame a 60 Hz.
Non applicare nuovamente il dt in secondi a questo step.

Il wrapper fisico contiene un ulteriore prodotto temporale. La provenienza del
suo scalar durante il normale update e il comportamento a diversi framerate
restano **UNKNOWN**; il rapporto misurato `1/60` non chiude questi punti.

## Animation relationship

**UNKNOWN:** legame effettivo fra parametro di velocità, selezione walk/run,
root motion e playback rate del player.

I metadati Phyre contengono `PCharacterMotionGait`, `m_speedMultiplier`,
`m_motionAnimSpeedScale` e `m_animSpeedLimit`. La loro presenza non dimostra
che governino la locomozione di CChrPc. Le osservazioni visive al 25/75/100%
non dimostrano che un multiplier Sprint manterrebbe sincronizzati passi e movimento.

## Recommended Sprint hook

**Prima candidata per un PoC:** risultato di `0x208FD0`, o suo consumo nel ramo
player di `0x205BC0`, prima della scrittura `+0x9F24`. **HIGH CONFIDENCE** come
punto a monte della posizione richiesta; **UNKNOWN** come hook sicuro per animazione
e combattimento. Nessun hook definitivo approvato dalle evidenze attuali.

| Candidato | Player-only | Animazione | Collisioni | Combat | Valutazione |
|---|---|---|---|---|---|
| Getter/consumo velocità `0x208FD0` | filtro istanza verificabile | UNKNOWN | HIGH CONFIDENCE se mantiene la pipeline | UNKNOWN | prima candidata |
| Modalità walk/run esistente | da verificare | UNKNOWN | da verificare | UNKNOWN | richiede soglia e selettore |
| Argomento Bullet | filtro KCC verificato | UNKNOWN | pipeline KCC conservabile | UNKNOWN | dt non risolto, seconda scelta |
| Delta posizione richiesta | filtro possibile | UNKNOWN | conservabile se passa dal KCC | UNKNOWN | maggiore rischio di disaccoppiamento |

Un futuro PoC deve filtrare il player attivo, conservare dt e modificatori,
e lasciare il movimento passare dal KCC. Non modificare la tabella globale,
gli NPC o la posizione finale. Nessuna collisione è stata alterata in questa
ricerca; la sicurezza di un futuro multiplier contro muri, scale e pendii
richiede comunque test. Nessuno Sprint implementato.

## Remaining unknowns

1. Caller runtime completo, registri e thread della submission Bullet.
2. Asse analogico effettivo, deadzone, curva e soglia walk/run; incongruenza al 75%.
3. Significato e stato attivo dei selettori del getter; eventuali altri writer.
4. Timestep del wrapper fisico e confronto a framerate diversi.
5. Animazione/root motion e risposta a una modifica della velocità.
6. Comportamento in città, combat e stati non controllabili.
7. Collisioni con multiplier: muri, scale, pendii e ostacoli non testati.

## Phase 1 Sprint readiness

**NOT READY — MOVEMENT-01/02 non completamente chiusi.**

| Requisito minimo | Stato |
|---|---|
| Player Bullet controller identificato | CONFIRMED |
| Caller locomotion identificato | HIGH CONFIDENCE static; trace runtime incompleto |
| Punto di produzione/scaling individuato | CONFIRMED static; corrispondenza runtime HIGH CONFIDENCE |
| Stick magnitude vs speed compreso | PARTIAL: quattro prove manuali; curva/soglia UNKNOWN |
| Dt abbastanza validato da evitare speedhack | PARTIAL: integrazione ricostruita; wrapper/framerate aperti |
| Hook Sprint consigliato con evidenze | candidato individuato; validazione animazione/combat assente |
| Collisioni Bullet preservate | pipeline attuale invariata; PoC non testato |

Prossimi passi: acquisire asse e selettori con cattura sincronizzata, ripetere
la zona di transizione walk/run, confrontare due framerate e tracciare il gait.
Audio, INPUT-01, STATE-01 e implementazione Sprint non avviati.
Modifiche lasciate non committate. Le quattro nuove firme salvate sono uniche
nella build verificata; sintassi Python, TOML e self-check del reader superati.
Durante le prove mod locali e servizi Special K sono stati disabilitati;
il ripristino dello stato iniziale non è stato ancora eseguito.
