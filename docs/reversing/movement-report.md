# SAOHRFix — Movement report

**Aggiornamento:** le sezioni fino a “Baseline readiness” conservano il report
manuale del commit `ddca350`. Le conclusioni correnti, che sostituiscono le sue
incertezze e lo stato finale storico, iniziano da “Analog input path”.
La decisione finale corrente è in **“COLLISION-SLOPE-04 — 2026-10-10”**:
**NOT READY**. Gli store della Y terreno sono identificati direttamente.
Il candidato vanilla-first con extra fisico separato evita la grande ascesa
nelle due prove, ma la seconda supera la fascia verticale dei controlli.
Resta un blocker: equivalenza e stabilità del primo contatto vanilla negli
update successivi agli extra. La causalità del nuovo picco non è dimostrata.

Data: 1 ottobre 2026. Build Steam PC, SHA-256
`1923f0d8d2cad559d6ad6e001af54ea5ea5aa70171323f42d4e1fa3d63699e43`.
Gli indirizzi di codice sono RVA, base modulo `0x140000000`.
Fonti del progetto: [player.md](player.md), [input.md](input.md),
[addresses.toml](../../research/addresses.toml),
[signatures.toml](../../research/signatures.toml).

Evidenze: **CONFIRMED** = istruzioni verificate o valori letti runtime;
**HIGH CONFIDENCE** = associazione sostenuta da più evidenze, senza trace completo;
**PROBABLE** = ipotesi da verificare; **UNKNOWN** = non dimostrato.
Le osservazioni manuali iniziali del gait sono dichiarazioni dell'utente;
le sezioni diagnostiche successive distinguono request/rate letti dal giudizio visivo.

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

## Baseline remaining unknowns

1. Caller runtime completo, registri e thread della submission Bullet.
2. Asse analogico effettivo, deadzone, curva e soglia walk/run; incongruenza al 75%.
3. Significato e stato attivo dei selettori del getter; eventuali altri writer.
4. Timestep del wrapper fisico e confronto a framerate diversi.
5. Animazione/root motion e risposta a una modifica della velocità.
6. Comportamento in città, combat e stati non controllabili.
7. Collisioni con multiplier: muri, scale, pendii e ostacoli non testati.

## Baseline readiness

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

## Analog input path

**CONFIRMED, static:** `205BC0` ottiene l'oggetto assi tramite globale `AEA4A0`
e `1CE560`. Chiamate `205C31 -> 2D0290` per X e `205C4B -> 2D04D0` per Y,
`edx=0`. Risultati signed16 inizialmente in R12D e R15D.
History ring RVA `C66D60`, stride `8C`, X/Y a `+80/+82`; count `C69060`,
cursor `C69068`. In modalità 64: `(cursor-1-edx) mod 64`.
Inversione possibile tramite byte dell'oggetto asse `+70E`, non acquisito runtime.
L'ultimo slot del ring letto per polling non è necessariamente quello consumato.

**CONFIRMED, runtime diagnostico:** all'ingresso player `1E9980`, con return
`1E993F` e outer return `206660`, R12D contiene **X²**, R15D **X²+Y²**, XMM2
il parametro prodotto. Gli assi con segno sono già persi in questo punto.
Osservati 10.201, 10.404, 16.129 e 16.384 come magnitudini quadrate consumate.
Interpretazione dei registri valida solo per questo caller verificato.

`virtual_pad.py` usa Xbox virtuale su ViGEmBus già presente. `vgamepad 0.1.3`
installato nella `.venv`, senza installazione di driver globale. Pad connesso
prima dell'avvio Steam; sweep a entrambi i segni, 2 s attivi e 1 s neutri:
0/10/20/30/40/50/60/65/70/75/80/85/90/95/100%.
Comandi ripetibili, ma trasformazione Steam/Input non calibrata universalmente:
in prove diverse la stessa percentuale ha prodotto valori interni diversi.
La classificazione usa quindi i valori consumati, non le percentuali comandate.

`analog_probe.py`: letture delimitate con timestamp monotonic e cursor prima/dopo;
non atomiche. Sweep valido circa 115 s: 114 record respinti per cambio cursor,
massimo intervallo di lettura 1,376 ms.
`walk_trace.py`: record KCC con sequence, parametro, flag, dt, vettore pre-wrapper
e argomento Bullet; copia anche l'ultima produzione e richiesta animazione.
Sequence prima/dopo filtrano copie instabili. Produzione e submission avvengono
su thread diversi: **ultima produzione non significa stesso frame**.
La guardia non dimostra serializzazione di eventuali writer concorrenti.
Timestamp di osservazione, non timestamp nativo comune a tutti gli hook.
L'acquisizione degli assi signed nel medesimo evento resta incompleta.

## Walk/run threshold or curve

**CONFIRMED, static:** `20646A` calcola la somma dei quadrati degli assi e la
confronta con `0x3100 = 12544 = 112²`. Sotto soglia azzera F8A6 e timer F838.
Sopra soglia, se `20AD30` consente il percorso, accumula `1E6090 -> 69B4C0`;
quando il timer supera 10 attiva F8A6 e lo azzera. Nella modalità temporale normale
sono circa 10/60 s. `20AD30` dipende da `1E6DA0` e `1E6D70`, semantica generale
ancora UNKNOWN. Il ramo tastiera può attivare F8A6: non è esclusivo dello stick.

| Asse X interno, Y=0 | F8A6 | +9F24 | Evidenza |
|---|---|---|---|
| +69/+85/+93/+101/+109 | 0 | 0,043 | CONFIRMED runtime |
| -70/-86/-94/-102/-110 | 0 | 0,043 | CONFIRMED runtime |
| +117/+125/+127 | 0 iniziale, poi 1 | 0,043 -> 0,1677 | CONFIRMED runtime |
| -118/-126/-128 | 0 iniziale, poi 1 | 0,043 -> 0,1677 | CONFIRMED runtime |

Sotto soglia circa 190–192 campioni per bin. A +117: 16 walk e 175 run;
a -118: 16 walk e 175 run. Bin esatti 111/112/113 non acquisiti:
frontiera precisa verificata staticamente, non misurata in quei bin.
Neutri con flag/parametro precedenti sono transitori esclusi dalla curva mobile.
Nessuna deadzone universale derivata da piccoli comandi senza movimento.

**HIGH CONFIDENCE:** nel field provato il parametro è quantizzato walk/run,
con soglia e ritardo. Non emerge proporzionalità continua del parametro alla
deflessione dentro queste fasce. Non estendere a tutti gli stati o alla velocità
reale dopo collisioni. Le percentuali manuali baseline non fissano la soglia.

## Selector semantics

**CONFIRMED, static:** player virtual `+648 = 20AB60` nega il risultato del
componente embedded `+A9E0`, vtable `80A8F0`; slot `+40 = 20A740`
chiama slot `+60 = 20A750`. Risultato:

```text
selector_648 = (CChrPc[A9E9] == FF && CChrPc[A9F0] == FE)
```

**CONFIRMED, runtime:** predicato vero in idle/walk/run e inversione;
F8AD=0 nelle fasce provate. Non chiamarlo IsRunning. Enum sottostanti UNKNOWN.
Nel ramo +648=true, F8A6=1 seleziona tabella `+30 = 3,9`; F8AD partecipa
all'altro fattore (`+18 = 1` nella build). Nel ramo false entrano +9F88 e
fattori `+34 = 3,9` / `+38 = 1,38`. Semantica generale F8AD non dimostrata.

**CONFIRMED, runtime diagnostico:** nella stessa chiamata di produzione per
l'istanza player, magnitudine consumata costante, stato A9E9=FF e pending A9F0=FE,
F8A6=0 coincide con parametro XMM2 0,043; F8A6=1 con **0,1677 = 0,043 × 3,9**.
Base +9F20 invariata e F8AD=0. Le istruzioni interne del getter non hookate:
branch ricostruito staticamente e input/output confermati all'ingresso del setter.

| Ultima cattura | Magnitudine² consumata | Primo walk osservato | Primo run osservato | Intervallo |
|---|---|---|---|---|
| +127 | 16.129 | 14,842476 s | 15,007770 s | 165,294 ms |
| -128 | 16.384 | 18,840674 s | 19,007919 s | 167,245 ms |

Tempi di polling, non misura esatta del timer nativo; coerenti con il ritardo.

## Runtime call confirmation

Shim log-only su copie private delle vtable delle istanze player/KCC:
player +3E8, player +460, KCC +18. Tail jump alle implementazioni originali;
scratch registers e flags preservati, argomenti originali invariati.
Nessun valore movimento/tempo/collisione modificato. Sono catture strumentate,
distinte dalla baseline di sole letture; nessuna patch permanente EXE/CPK.

- **CONFIRMED runtime:** `205BC0` raggiunge `1E9980` tramite `1E98A0`,
  return `1E993F`, outer return `206660`; thread worker variabili.
- **CONFIRMED runtime:** return Bullet `58D31F` dentro `58CF40`,
  return wrapper `6CC141` dentro `6CC090`, manager `6CBDA5` dentro `6CBD80`.
- Ultima cattura: 8.889 submission, 5.729 record osservati, circa 60 s;
  submission thread 76948. Thread ID non permanente.
- Tratto integrazione/posizione richiesta fra gli estremi ricostruito staticamente;
  non acquisito come singolo stack completo. Le copie dell'ultimo evento non lo
  ricostruiscono né dimostrano identità di frame.

Ultima sessione valida PID 52256, CChrPc VA 0x213A7890, physics ID 10,
wrapper VA 0x20CD0D60, KCC VA 0x80DF9CF0. Tutte VA session-only.
Vptr originali ripristinati dopo le catture. Ogni trace conserva pagina privata
di 4 KiB nelle prime versioni, 8 KiB nella finale, fino a uscita gioco: non liberata
mentre un thread potrebbe attraversarla. Nessun hook attivo al termine.

## Framerate behavior

**CONFIRMED static:** writer 69B430, callsite 696143, dt A63238, reciproco A6323C,
`A63240 = clamp(dt × 60, minimum, maximum)`. Getter 69B4C0 usa questo step
in modalità normale, A63248×60 in fixed mode; scala player +9FE8 osservata a 1.

**CONFIRMED static/runtime:** `6CBD98` carica costante da **81FD40**,
float **1/60 = 0,0166666675**, per l'update fisico. Il vecchio RVA 820D40 era
un errore di calcolo. All'ingresso KCC lo scalar è in **XMM6**;
XMM9 è già sovrascritto dal vettore, escluso dalle misure temporali.
Wrapper+F4=60 in movimento: pre-wrapper ×60 e poi ×1/60 restituiscono circa
il pre-wrapper all'argomento Bullet, entro arrotondamento float.
Esempio run: pre `(0,039585114; 0,009484291; -0,068557739)`,
KCC `(0,039585110; 0,009484290; -0,068557732)`.

Il tempo è già incluso nell'integrazione gameplay. Non moltiplicare di nuovo
lo spostamento Bullet per app dt o 60. Mediane `|KCC_XZ|/app_dt` circa 2,58 walk
e 10,062 run, compatibili con parametro×60; sono rapporti di spostamento
**richiesto**, non velocità reale misurata dopo collisioni.
Dt circa 6–8 ms nelle catture non certifica il render FPS.

**UNKNOWN / blocker:** confronto verificato 30/60/120 FPS e distanza reale su
intervallo lungo. Nessun controllo FPS trovato nelle tre pagine Options in-game
ispezionate; nessun limiter RTSS operativo rilevato. Non prova assenza di altri
controlli. Nessun progetto graphics introdotto per aggirare il test.
Indipendenza reale dal framerate non dichiarata.

## Animation/gait relationship

**CONFIRMED static/runtime:** player virtual +460 = 1DDC10 riceve request ID,
canale, flags e rate. Scrive rate +90F0, request short +90F8; consumer 1F6730
inoltra all'owner +4C0 e resetta ID/rate. Polling ordinario perde quasi tutte le
richieste; lo shim registra gli argomenti all'ingresso. Writer rate canale 287E90
scrive +1E8, non campionato continuamente.

| Evento associato | Request ID | Rate richiesto | Canale | F8A6 all'ingresso |
|---|---|---|---|---|
| idle | 0 | 1 | 0 | 0 |
| walk | 100 | 2 | 0 | 0 |
| run | 122 | 1 | 0 | 1 |
| altra richiesta durante run | 246 | 1 | 0 | 1 |

**CONFIRMED:** valori grezzi, caller 2B7FDE/2B7EFF, altre richieste da
2C44E1/2C4AD0. **HIGH CONFIDENCE:** associazione walk/run e selezione animazione
esistente. ID numerici non sono nomi finali di clip; 246 non identificato come
Sprint. L'ultima richiesta può restare nel record dopo cambio flag: nessuna
promessa di cambio gait nello stesso frame. I timestamp degli eventi del logger
sono di prima osservazione; le catture iniziali conservavano ultima osservazione.
Nessuna durata precisa di clip dedotta da questi tempi.

Rate getter +4B8 = 209370: nel ramo exploration osservato dipende da 1E6DA0,
virtual +8D8 = 207FA0, 1E6D70 e F8AD; quel ramo non usa direttamente F8A6.
Altro ramo combina 208FD0 e metadata 1E4C00, non dimostrato attivo nelle prove.
Modificare solo 208FD0 non garantisce playback proporzionale. Blending,
root motion, contatto piedi e risposta a multiplier **UNKNOWN**.
Metadati Phyre baseline restano piste, ownership non dimostrata.

## Sprint hook recommendation

Modalità più veloce **già confermata**: run selezionata da F8A6 dopo soglia e
ritardo, accompagnata da richiesta animazione differente. Non trovata una terza
modalità Sprint verificata. Forzare run da walk riuserebbe il comportamento,
ma non aumenterebbe il run a stick pieno. Non forzare enum A9E9/A9F0 o F8AD.

Per futuro PoC **1,25×**, candidata: consumo/risultato 208FD0 nel ramo player
205BC0, prima dello store +9F24, filtrando l'istanza attiva e conservando i
modificatori. Subordinato a chiusura FPS e animazione: nessun hook velocità validato.
Evitare scrittura ripetuta +9F24, tabella globale, global dt, NPC, posizione finale
e argomento Bullet; mantenere pipeline KCC. Raccomandazione attuale:
**non applicare multiplier** finché i blocker non sono chiusi.

## Sprint PoC results

**Non eseguito:** condizione esplicita di avvio non soddisfatta, confronto FPS
e coupling animation/playback incompleti. Nessun toggle o multiplier installato.

## Collision tests

Nessuna prova con multiplier: tunneling, sliding, jitter, penetrazione, scale
e pendii non validati. Prove base con movimento/inversione in field e KCC
originale. Città e combat non testati nella continuazione; nessuna dichiarazione
di Sprint sicuro in questi contesti.

## Remaining unknowns

1. Confronto controllato 30/60/120 FPS, distanza reale e comportamento dei clamp.
2. Rate finale, blending/root motion e risposta animazione a multiplier.
3. Signed X/Y consumati nel medesimo evento produzione; slot ring e inversione
   senza identità di frame comune. Nessuna falsa atomicità fra worker.
4. Percentuale virtuale -> unità interne, deadzone e frontiera runtime esatta;
   confronto 112² statico, nessun bin 112 isolato acquisito.
5. Enum A9E9/A9F0, significato generale F8AD/20AD30, combat/città.
6. Writer intermedi e altri percorsi di movimento, terza modalità oltre run.
7. Sicurezza futuro PoC su collisioni/terreno e sincronizzazione dei piedi.

## Phase 1 Sprint readiness

**NOT READY.** Sorgente e ramo walk/run confermati; FPS e animazione bloccano PoC.

| Requisito | Stato |
|---|---|
| Player filtrabile e controller/backlink | CONFIRMED runtime |
| Branch 0,043 -> 0,1677 | CONFIRMED static + runtime diagnostico |
| Magnitudine consumata e soglia walk/run | CONFIRMED; signed assi sincronizzati incompleti |
| Wrapper scale/scalar, evitare doppio dt | CONFIRMED nel percorso provato |
| Framerate independence | UNKNOWN / blocker |
| Selezione gait/animation | HIGH CONFIDENCE; playback con multiplier UNKNOWN |
| Collisioni | pipeline originale preservata; PoC/test assenti |
| Combat/città e hook Sprint validato | UNKNOWN |

## Stato finale della continuazione

Gioco valido avviato da Steam con pad virtuale già connesso. Mod locali
**rimaste disabilitate reversibilmente**, senza cancellazione:

- `W:\SteamLibrary\steamapps\common\SAOHR\d3d11.dll.saohrfix-off`
- `W:\SteamLibrary\steamapps\common\SAOHR\SAO HR Ultrawide.asi.saohrfix-off`

Servizi global injection Special K arrestati. Nessun modulo Special K/ASI/ReShade
rilevato nel processo valido; D3D11/DXGI da System32. DSX e driver preesistenti
non rimossi. Vptr diagnostici ripristinati; pagine private fino a game exit.
Pad virtuale della prova disconnesso al termine. Nessun ripristino automatico
delle injection durante la sessione vanilla.
Audio, INPUT-01/STATE-01 generali, graphics, ImGui e Sprint non avviati.

Baseline e risultati conservati in commit separati. Verifiche finali:
self-check reader/pad/probe/shim, sintassi Python/TOML e unicità firme build-local.
Solo sorgenti/documentazione; nessun dump, grande cattura o binario proprietario.

## Continuazione FPS/animation — 2026-10-01: conclusione corrente NOT READY

Decisione diagnostica prima della prova: usare il consumo del risultato tramite
il setter player `1E9980`, slot `+3E8`, chiamato da `1E993F` nel percorso
`206660`, prima dello store originale in `+9F24`. Questo punto evita un detour
nel corpo condiviso di `208FD0` e riusa la copia del vtable della sola istanza.
Il parametro in ingresso XMM2 viene moltiplicato solo per il player risolto,
physics ID invariato, F8A6=1, F8AD=0, state=FF/pending=FE, entrambi i return
address verificati e parametro originale esattamente `0.1677`. Solo fattori
1.10/1.25. Nessuna modifica di dt, tabelle, Bullet, NPC o posizione finale.
Questa scelta non costituisce ancora una validazione dell'hook Sprint.

### Controlled FPS test

**CONFIRMED runtime:** limiter NVIDIA applicato al solo profilo esistente di
`sao_hr.exe` tramite NVAPI DRS. Nessuna injection aggiunta e nessuna scrittura
al time scale del gioco. Override originale assente (`SETTING_NOT_FOUND`).
Il cap salvato a 30 produceva app dt circa 0.06666 s (~15 aggiornamenti/s).
Cambiarlo a 60 con il processo ancora vivo non modificava la cadenza.
Dopo riavvio da Steam con cap 60, app dt circa 0.03333 s e ~30 submission KCC/s.
Il valore del cap non è una misura indipendente del render FPS.

**UNKNOWN:** confronto controllato di velocità reale a ~30/60/120. Nessuna
seconda condizione con percorso piano e input valido è stata completata.
L'ultima cattura di 45 s era a riposo: 1345 submission, nessun segmento in
movimento. Non usarla come prova di framerate independence.

### Real movement speed

**CONFIRMED runtime/static:** `[KCC+0x10]` punta al ghost Bullet, vptr RVA
`8C3F08`; origine world transform a `ghost+0x40`. XZ coincide a riposo con
`CChrPc+0x9DE0`; Y ha offset di centro capsula di circa 1.4. La misura usa
tempo monotonic e posizione fisica; resta un poll non atomico.

Tratte preliminari con cap 30, app ~15 Hz, senza perturbazione:

| Input interno | Tempo s | Distanza netta XZ | Velocità XZ | Escursione Y | Utilizzabilità |
|---|---:|---:|---:|---:|---|
| (0, +127) | 4.8494 | 1.3442 | 0.2772 | 0.2819 | Bloccato presso ostacolo |
| (0, -128) | 4.8576 | 45.6614 | 9.4000 | 2.5279 | Terreno irregolare |

Entrambe avevano parametro run `0.1677`, pre-wrapper/KCC coerenti e
KCC XZ/app_dt circa 10.062. Il grande scarto della prima tratta dimostra
perché la richiesta KCC non sostituisce la distanza reale. Entrambe escluse
dal confronto su piano. Un'altra cattura con posizione `+9DE0`, precedente
all'uso del ghost, attraversava terreno irregolare ed è anch'essa esclusa.
I tool ora riportano anche lunghezza del percorso XZ, oltre alla distanza
netta; nessun risultato nuovo di tale metrica è disponibile in movimento.

### DT clamp behavior

**CONFIRMED runtime:** minimo RVA `C82FA8` = **0.0**, massimo `A63244` =
**60.0**. Con app dt ~0.06666 il valore `A63240` era ~4; con dt ~0.03333
era ~2. Entrambi lontani dal massimo. A 30 aggiornamenti/s, `dt*60` ~2
non si avvicina al clamp. Non confondere aggiornamenti app con render FPS.
Nessuna prova di saturazione del clamp eseguita.

### Animation downstream rate

**CONFIRMED static:** `28B720 -> 287E70` seleziona il canale del controller
tramite `+2F0 + 8*index`; `287E90` scrive il rate a `channel+1E8`.
Slot `+30` del vtable `822AE8` chiama `6C6C80`: restituisce
`[A65970] * [channel+1E8]`. `A65970` letto runtime = **1.0**:
è un fattore globale, non app dt.

`2888A0` chiama tale slot a `2888C9`, return address `2888CC`, passa XMM0
in XMM1 a `6C5A00`, che salva `channel+1D0`, poi entra in `6C5360`.
Nel suo blocco continuato `6C550F`, l'istruzione `6C5619` legge `+1D0`
in XMM2 e `6C5621` chiama `56E530`. Quest'ultimo seleziona un record
animation di stride `B0`, salva il parametro a `record+C` e `record+50`
e aggiorna `+54`. Questa è la catena del parametro di playback individuata;
durata del clip e fase effettiva nel tempo restano **UNKNOWN**.

**CONFIRMED runtime diagnostico, riposo:** getter osservato con caller
`2888CC`, campo `+1E8=1.0`, risultato `1.0`; poll finale `+1D0=1.0`.
I log sono stati osservati su più worker thread: conteggi riportati sono
campioni, non conteggi esatti di chiamate; letture cross-thread non atomiche.
Baseline storica walk request 100/rate 2 e run request 122/rate 1 preservata.
Nessuna nuova baseline downstream walk/run sincronizzata acquisita.

### Perturbation 1.10x

**UNKNOWN / non eseguita.** `run_perturb.py` è preparato e passa self-check
del codice macchina e dei nove filtri, ma non è stato avviato sul gioco.
Nessun dato su velocità reale, sliding, gait o root-motion conflict.

### Perturbation 1.25x

**UNKNOWN / non eseguita.** La stabilità a 1.10 non è ancora dimostrata.

### Collision sanity

**UNKNOWN con perturbazione.** Il rallentamento presso l'ostacolo riguarda
solo la baseline originale. Non convalida muro, svolta stretta, pendenza,
scale, stop o inversione con moltiplicatore.

### Town/combat sanity

**UNKNOWN / non eseguita:** manca prima la validazione del field.

### Final Sprint architecture

**PROBABLE candidata, non finale:** consumo del risultato locomotion nella
sola istanza player, prima dello store originale, mantenendo wrapper/KCC e
compensazione dt originali. Non applicare un secondo dt. Il filtro diagnostico
usa identità/physics ID e stato già run; non forza F8A6 o stati.
La risposta animation A/B/C/D non è classificabile. Nessun hook animation
aggiuntivo scelto e nessuna equivalenza fattore-speed/fattore-rate assunta.
Nessuna specifica PoC autorizzabile finché i test non chiudono questi punti.

### Phase 1 readiness

**NOT READY — conclusione corrente.** Aggiunti clamp effettivi, posizione
world fisica e catena downstream rate. Restano confronto FPS con movimento
reale, baseline downstream walk/run, 1.10/1.25, classificazione animation,
collision sanity e town/combat. Non è stata implementata una feature Sprint.

### Cleanup e interruzione

Computer Use interrotto dall'utente con Escape: esperimenti arrestati, nessun
ulteriore comando UI. La finestra era uscita dal desktop accessibile; una
richiesta di disponibilità era ancora pendente. Un impulso senza il campo
obbligatorio `buttons` è stato rifiutato dal server pad prima dell'invio;
il dispositivo è stato riconnesso, poi disconnesso nel cleanup.

Tre vptr verificati dopo la cattura: player `80AE08`, KCC `879BD0`, channel
`822AE8`. Nessuna perturbazione o patch attiva. Pagina privata diagnostica
di 8 KiB mantenuta fino all'uscita del processo per evitare return in memoria
liberata. Gioco PID session-only 83096 lasciato aperto e rispondente.
Override NVIDIA eliminato e assenza originale verificata (`fps: null`);
la cadenza dell'istanza già avviata può conservarsi fino al prossimo riavvio.
Pad virtuale disconnesso; nessun driver installato o rimosso.

Mod locali ancora disabilitate reversibilmente: `d3d11.dll.saohrfix-off` e
`SAO HR Ultrawide.asi.saohrfix-off`, nessuna mod locale attiva. Special K
non riattivato. La baseline vanilla precedente rimane preservata.
Self-check shim, analog probe, perturbation e limiter passati. Nuovo codice
perturbazione validato solo staticamente: il self-check non prova il suo
funzionamento live. Nessuna analisi Audio o altra fase avviata.

## Current validation — 2026-10-01

Questa sezione sostituisce la decisione finale precedente. Input Xbox virtuale
attraverso Steam; nessun intervento manuale richiesto durante le nuove prove.
Le catture con shim sono diagnostiche, con chiamate originali preservate.
Processi Steam puliti verificati senza Special K/ReShade/mod locali; una prima
istanza con Special K caricato è stata esclusa prima di installare gli shim.
Indirizzi heap e PID citati sono validi soltanto nella relativa sessione.

### Controlled FPS test

**CONFIRMED runtime:** profilo NVIDIA esistente, cap 30/60/120 e riavvio da
Steam. Contatore dell'overlay NVIDIA osservato tramite Computer Use a **30**
e **120–121 FPS**, anche durante movimento. Sono misure del contatore esterno,
non un trace Present né una misura della regolarità di ogni frame.

| Cap driver | FPS osservati | Mediana app dt, s | Step A63240 | Cadenza movimento app |
|---|---:|---:|---:|---:|
| 30 | 30 | 0.066664–0.066669 | 3.9998–4.0001 | circa 15 Hz |
| 60 | non misurati dal contatore | 0.033318–0.033327 | 1.9991–1.9996 | circa 30 Hz |
| 120 | 120–121 | 0.016663 | 0.9998 | circa 60 Hz |

Non chiamare app dt 16.7 ms una misura di render 60 FPS: qui il contatore
riporta 120 FPS. L'origine della differenza di cadenza resta **UNKNOWN**.
Le condizioni 30 e 120 soddisfano il confronto fra due target molto diversi.
Il cap 60 ha una baseline fisica, ma la sua cadenza render non è stata verificata.

### Real movement speed

**CONFIRMED runtime:** posizione fisica `ghost+40`, tempo monotonic. Tratto
campo circa X=-6.5/-6.7, Z=132–183, escursione verticale circa 0.50–0.54
su 48 unità XZ: quasi piano, non matematicamente piano. Input virtuale
(-0.8660254,-0.5) e inverso, consumato come (-111,64)/(110,-64).
Stesso corridoio e due direzioni; stati run contigui dopo la transizione walk.

| Condizione baseline | Direzione | Tempo, s | Distanza netta XZ | Velocità netta | Velocità percorso | Escursione Y |
|---|---|---:|---:|---:|---:|---:|
| cap 30, contatore 30 | andata | 4.8003 | 48.2869 | 10.0591 | 10.0591 | 0.5005 |
| cap 30, contatore 30 | ritorno | 4.8035 | 48.2960 | 10.0544 | 10.0544 | 0.5077 |
| cap 60, ripetizione senza moltiplicazione effettiva | andata | 4.8031 | 48.2939 | 10.0547 | 10.0547 | 0.5310 |
| cap 60, stessa cattura | ritorno | 4.8332 | 48.4731 | 10.0291 | 10.0422 | 0.5354 |
| cap 120, contatore 120–121 | andata | 4.8167 | 48.4482 | 10.0584 | 10.0584 | 0.5076 |
| cap 120, contatore 120–121 | ritorno | 4.8385 | 48.6259 | 10.0498 | 10.0504 | 0.5119 |

La ripetizione cap 60 era il primo tentativo ×1.10, con filtro mai soddisfatto:
parametro e submission rimasti vanilla. È utilizzabile come baseline diagnostica,
non come prova riuscita del multiplier. Lo scarto fra medie andata/ritorno a
30 e 120 è circa **0.03%**; non attribuire precisione superiore al poll.
**HIGH CONFIDENCE:** velocità reale sufficientemente indipendente dal target
nel corridoio esplorazione verificato. Non estendere il risultato a ogni stato.

Le prime tratte contro roccia/pendenze e il primo allineamento cap 30 a X≈10,
con escursione Y 1.10–1.44, sono esclusi. Il primo giro longitudinale cap 60
aveva deviazione all'andata (9.8289 netta/9.9435 percorso); usare la ripetizione.
Walk separato: 2.9624 s, 7.6515 unità XZ, **2.5828 unità/s**, parametro
0.043, escursione Y 0.5424; non è una verifica walk a tutti i framerate.

### DT clamp behavior

**CONFIRMED runtime:** minimo 0, massimo 60. A render 30 FPS, app dt circa
0.06667 e `dt*60` circa **4**, appena 1/15 del massimo. Non c'è saturazione
nel test. Submission KCC/dt baseline circa **10.062** in tutte le condizioni;
wrapper scala 60 e dt wrapper 1/60 restano invariati. La velocità fisica
conferma che il percorso osservato non applica una seconda integrazione dt.
Pause lunghe/saturazione e altri contesti restano **UNKNOWN**.

### Animation downstream rate

**CONFIRMED runtime:** request walk 100/rate 2, run 122/rate 1. Getter
`6C6C80`, return `2888CC`, restituisce effettivamente 2/1; `channel+1E8`
e `channel+1D0` riportano gli stessi rate nei segmenti stabili.
La catena statica continua tramite `6C5A00 -> 6C5360 -> 56E530`, con rate
salvato nel record animazione e usato nell'update. `A65970=1` è il fattore
globale del getter, non app dt. Non modificarlo.

`channel+1D4` cambia e fa wrap: coppie inizio/fine, per esempio run baseline
cap 30 circa 8.00→11.93, ×1.25 circa 8.18→19.98. Le coppie attraversano
più cicli e non misurano una durata clip. Unità, durata e fase del contatto
piede restano **UNKNOWN**; non ricavare un factor animazione da questi numeri.
Un breve rate 2 iniziale è la transizione walk, non playback stabile run.

I poll world/rate non sono un frame atomico. Il log del getter è condiviso
fra worker e non usa un contatore atomico: campioni/eventi possono perdersi.
Le copie production/animation possono riferirsi alla chiamata precedente;
evitare di classificare gait da un singolo primo record in movimento.

### Perturbation 1.10x

**CONFIRMED runtime:** setter player slot +3E8, `1E9980`, return `1E993F`,
outer `206660`, XMM2 prima dello store originale +9F24. Il target +9E20
è già costruito, ma il downstream normalizza target-current e integra usando
il parametro: l'aumento fisico misurato esclude un effetto soltanto informativo.

Il filtro iniziale confrontava float32(0.1677), bits `3E2BB98C`;
il risultato vanilla reale è **`3E2BB98D`** (un ULP superiore). Primo tentativo
senza effetto, poi confronto corretto e self-check aggiunto. Tutti gli altri
filtri preservati: istanza, physics ID, F8A6/F8AD, state/pending, due chiamanti.

Parametro effettivo **0.1844700128**. Cap 60, andata/ritorno:
4.8338/4.8094 s, 53.4749/52.9701 XZ, velocità netta **11.0627/11.0139**,
percorso **11.0633/11.0280**; KCC/dt **11.0682**. Base 0.043 e walk invariati.
Run request 122, rate richiesto/getter/+1D0 **1.0**. Nessun crash nelle prove.

### Perturbation 1.25x

**CONFIRMED runtime:** parametro **0.2096250057**, KCC/dt circa **12.5775**.

| Condizione | Direzione | Tempo, s | Distanza XZ | Velocità netta | Velocità percorso |
|---|---|---:|---:|---:|---:|
| cap 60 | andata | 3.8009 | 47.7894 | 12.5731 | 12.5731 |
| cap 60 | ritorno | 3.8052 | 47.5901 | 12.5064 | 12.5283 |
| contatore 30 | andata | 3.8004 | 47.7939 | 12.5759 | 12.5760 |
| contatore 30 | ritorno | 3.7961 | 47.4335 | 12.4952 | 12.5358 |

Escursione Y circa 0.52–0.53. Run request 122 e rate downstream **1.0**.
**Case B CONFIRMED:** movimento aumenta, rate animazione resta normale.
Non osservato un cambio gait stabile nei log. **UNKNOWN:** quantità di foot
sliding visivo e root-motion conflict; screenshot isolati non bastano a
misurare contatto piedi. Nessuna prova di un rate animazione corretto aggiuntivo.

### Collision sanity

**CONFIRMED runtime:** tratto quasi piano, start/stop e inversioni dopo
rilascio completati. A ×1.25/cap 30, dopo rilascio due letture +9DE0 a
un secondo di distanza sono identiche in XZ (delta 0). Questo non misura
la latenza iniziale di arresto. Nessun crash o perdita dell'istanza.

**Problema da risolvere, test interrotto:** input world circa -X presso muro
in rovina, ×1.25/cap 30: da (-7.635,1.400,131.370) a
(-21.823,13.401,131.564) in 3.7905 s; escursione Y **12.0007**.
L'uscita inversa è tornata a quota normale, escursione Y 12.8185.
Screenshot durante contatto: camera occlusa dalla parete, insufficiente per
confermare penetration del personaggio.

Confronto vanilla successivo, stessa direzione e zona, da
(1.131,1.400,130.672) a (-18.485,1.594,131.301) in 3.7924 s:
velocità netta 5.1750, escursione Y **0.1982**; inversione regolare.
Partenze e traiettorie differiscono: **HIGH CONFIDENCE candidato a regressione
presso muro/pendenza**, non prova causale di tunneling né di geometria identica.
Va ripetuto con partenza/lane corrispondenti, prima di qualunque rollout.
Nessun altro incremento provato dopo l'anomalia. Curva stretta, scale,
pendenza controllata, ground contact, jitter e bouncing restano **UNKNOWN**.
Gli ultimi impulsi di svolta erano dopo il ripristino: non contarli come
collision sanity con multiplier.

### Town/combat sanity

**UNKNOWN / non eseguita:** il requisito di superare il field non è soddisfatto.
Nessun tentativo di forzare altri branch o mantenere hook durante cambio area.
**Exploration-only recommended** come limite per la prossima diagnostica,
non come dichiarazione di sicurezza o prontezza. Combat/città esclusi finché
non sono risolti il comportamento vicino al muro e il filtro di contesto.

### Final Sprint architecture

**HIGH CONFIDENCE candidato movement:** consumo setter player `1E9980`
prima di +9F24, con filtri verificati e moltiplicazione del risultato originale
una volta sola. Le prove ne confermano l'effetto fisico nel run esplorazione.
Non è ancora un hook Sprint approvato: il filtro bits esatto è diagnostico
e non copre variazioni di statistiche/buff o tutto il ciclo di vita player.

**Case B richiede un secondo hook player-only.** Punto minimo candidato:
return del getter rate `6C6C80`, slot +30 della sola istanza channel del
player (già intercettato senza alterazioni per il log). Moltiplicare il return
originale XMM0 soltanto quando la futura attivazione Sprint è valida e il
request run 122/canale è quello verificato; altri clip e NPC invariati.
È una proposta sostenuta dalla catena downstream, non una calibrazione live.
Non assumere animation factor=movement factor. Riconfermare il canale dopo
respawn/cambio area; preservare ABI e gestire worker concorrenti e teardown.

Nessun default finale, binding, config o feature implementata. Nessuna modifica
di global dt, tabella globale, argomento Bullet o posizione finale. Prima
chiudere la collisione sospetta, poi calibrare playback e validare altri contesti.

### Phase 1 readiness

**NOT READY.** Il confronto fisico a FPS diversi, clamp, assenza di double-dt
nel percorso verificato e perturbazioni ×1.10/×1.25 sono ora sostenuti da prove.
Il caso animazione B è identificato, ma la correzione non è calibrata.
Il sanity presso muro ha prodotto un'anomalia seria ancora da isolare: manca
la condizione “nessun problema collisione evidente”. Non avviare Sprint o Audio.

### Cleanup corrente

Vptr finali letti e verificati: player `14080AE08`, KCC `140879BD0`, channel
`140822AE8`. Tutte le catture hanno eseguito il ripristino in finally.
Gioco chiuso: le pagine private diagnostiche sono terminate col processo.
Pad neutralizzato/disconnesso; override NVIDIA eliminato, presenza originale
assente verificata (`fps: null`). Overlay prestazioni NVIDIA riportato spento.
Nessun driver installato/rimosso, eseguibile o archivio modificato.

Mod locali preservate nello stato iniziale disabilitato:
`d3d11.dll.saohrfix-off`, `SAO HR Ultrawide.asi.saohrfix-off`.
Special K 32/64 era Running a inizio ripresa; fermato per le catture e
riattivato dopo chiusura del gioco, ripristinando lo stato precedente.
Self-check runtime reader, analog probe, walk trace, perturbation e FPS limiter
passati. Commit separato dei soli tool/documentazione; nessun dump/capture grezzo.

## Current Sprint gate — collision reproduction and playback, 2026-10-01

Questa sezione sostituisce la decisione precedente. **NOT READY**.
I prerequisiti MOVEMENT-01/02 consolidati restano validi; nessun'altra fase iniziata.

### COLLISION-REPRO-01 setup and exclusions

Input tramite `virtual_pad.py`, ViGEmBus esistente, lancio Steam vanilla.
Cap NVIDIA richiesto **30**, dt app mediano circa **0.06666 s**. Il contatore
esterno non è stato riaperto in questa sessione: non è una nuova misura FPS.
Camera non manovrata, nessun input allo stick destro. Impulso al muro:
`x=-0.5, y=0.8660254, buttons=0`, **4.0 s**, poi neutro. Direzione world
richiesta quasi -X, con piccola componente +Z; assi consumati **(-65,-111)**.
La direzione della richiesta è registrata, non un nuovo offset yaw del player.

Ritorno pilotato dal pad con feedback read-only su XYZ, nessun teleport/write
della posizione. Target nominale ghost **(-7.673, 1.400, 131.388)**.
Il setup NON è bit-identico: il campionamento dell'input e la fisica quantizzano
il punto di arresto. Gli XYZ effettivi sono riportati sotto; non chiamare questo
un confronto con identica traiettoria fisica. L'input e la durata sono identici.
PID iniziale utile `61044`, player `213C2890`; dopo reload `77596`, player
`213BD890`. Indirizzi solo di sessione. Nessuna mod locale caricata; servizi
Special K fermati durante le catture.

**CONFIRMED runtime:** nel primo processo il selector è passato da `FF` a `1`,
con run parameter **0.1090050042** e clip **100122**, invece di 0.1677/122.
Il filtro esistente ha correttamente soppresso la moltiplicazione. Il significato
completo di selector 1 è **UNKNOWN**: non chiamarlo combat sulla sola base del
numero. Escluse come prove Sprint `100-2/3`, `110-1/2/3`, `125-4/5` e la prima
baseline animation. Quindi le due lane adiacenti NON dimostrano stabilità ×1.25.
Un primo avvicinamento partito da altra posizione è stato escluso separatamente.
`run_perturb.py` ora rifiuta l'avvio fuori dal selector verificato **FF/FE**.

File locali `.cache/collision-original-<factor>-<run>.jsonl`, ignorati da Git.
Tutte le partenze seguenti hanno ghost Y=1.400. Il parametro effettivo, non il
nome del file, conferma l'attivazione: 1.00 → 0.1677000076;
1.10 → 0.1844700128; 1.25 → 0.2096250057.

| Factor / run | Start X | Start Z | Max ghost Y | Detector events |
|---|---:|---:|---:|---:|
| 1.00 / 1 | -7.6729 | 131.3875 | 1.6011 | 0 |
| 1.00 / 5 | -7.7246 | 131.4068 | 1.5971 | 0 |
| 1.00 / 6 | -7.7688 | 131.4069 | 1.5966 | 0 |
| 1.00 / 7, confronto successivo | -7.4314 | 131.4036 | 1.6380 | 0 |
| 1.10 / 4 | -7.8038 | 131.4064 | **3.7950** | **9** |
| 1.10 / 5 | -7.4889 | 131.3863 | 1.6138 | 0 |
| 1.10 / 6 | -7.7938 | 131.4064 | 1.7439 | 0 |
| 1.25 / 1 | -7.4718 | 131.4006 | 1.6452 | 0 |
| 1.25 / 2 | -7.6900 | 131.4227 | 1.6422 | 0 |
| 1.25 / 3 | -7.5564 | 131.4245 | 1.6427 | 0 |
| 1.25 / 6, dopo reload | -7.6345 | 131.3846 | 1.6442 | 0 |

Baseline aggiuntiva `100-4`, Z=131.4999, max Y=1.5950: altra lane, non usata
nel confronto principale. Le correzioni che non hanno superato il gate di
posizione non hanno avviato una cattura/hook.

### Vertical event: source narrowed, trigger unresolved

`walk_trace.py` conserva ora campioni con ghost/player XYZ, target player +9E20,
requested KCC vec, +9F24, assi consumati, tempo monotonic, delta XYZ fra campioni,
campi KCC +20/+24, +40/+44/+48 e bytes +E0..+E3. Detector:
`abs(sample deltaY)>0.5` oppure `abs(Y-startY)>2.0`.
Sono letture sequenziali, NON frame atomici. Un delta può attraversare più update.

**CONFIRMED static:** getter KCC `729EC0`, vtable +58, restituisce onGround quando
entrambi i float **+20 e +24 sono zero**. Il predicato è replicato read-only.
Non è una misura di contatto piede/terreno. +44 è lo step-height usato dal ramo
step-up `72AE80`; valore runtime **0.035**, +48 **0.02**. Gli altri flags restano
grezzi; nessun nome inventato per touching contact.

**CONFIRMED runtime, 110-4:** Y sale da 1.400 a **3.795**, poi ritorna a 1.408.
Durante la salita il clip attivo è **246**, il parametro diventa **0.5 originale**
e il caller del setter è **1F625A**, non 1E993F/206660. Lo shim non moltiplica
questo ramo. Esempio: ghost (-18.9486,3.0510,131.5546), player Y=1.6510,
target player Y=2.0868, pre-wrapper/KCC requested Y circa **+0.61936**.
Il predicato onGround campionato è vero, campi verticali +20/+24=0; flags
campionati (1,0,1,0). Picco deltaY campionato **1.0643**, non dichiarato come
singolo frame. L'animazione corretta non era attiva in questa prova.

**CONFIRMED static:** `1F6219` carica XMM2 dalla costante `904F90` (=0.5),
`1F6254` chiama player virtual +3E8, return **1F625A**. Il ramo considera +A025,
+9FDC e +9FF8; non sono ancora identificati tutti i writer/trigger.
**HIGH CONFIDENCE:** questo evento verticale è richiesto dalla locomotion
upstream e da un'altra azione, non generato soltanto dalla correzione verticale
di Bullet. **PROBABLE:** azione di salto/superamento ostacolo associata a 246;
non assegnare ancora un nome definitivo al clip.

La cattura storica **1.4 → 13.4** NON è stata riprodotta integralmente.
Il nuovo evento più piccolo non prova che abbia la stessa causa. Le baseline
vicine non hanno attivato 246; il trigger intermittente resta **UNKNOWN**.
Nessuna conclusione di tunneling/penetration, né soglia sicura 1.20 dedotta.
Il problema non è monotono nel factor: un evento a 1.10 e quattro prove stabili
a 1.25 non autorizzano un default inferiore senza identificarne il trigger.
Boundary 1.15/1.20 e sanity scale/curve/pendenze rinviati a questo gate.

### Player-only animation return calibration

**CONFIRMED static:** `286F80` ricava l'ID attivo tramite `6C5E30`:
indice `channel+114`, descrittori `[channel+A8]`, count `channel+B8`, stride
**40 bytes**, ID nel descrittore **+18**. `6C48B0` verifica l'indice e risolve il
descrittore. **CONFIRMED runtime:** FF/FE usa idle **0**, walk **100**, run
**122**; il contesto selector 1 osservato usa 100000/100100/**100122**.
Non usare la sola request temporanea player+90F8: il consumer la azzera.

Il diagnostico chiama l'originale **6C6C80** e moltiplica soltanto XMM0 restituito
dalla singola istanza channel zero risolta dal player. Filtri: activation byte
privato, physics ID, F8A6=1/F8AD=0, FF/FE, parametro movement effettivo atteso,
owner/controller/channel invariati, RCX corretto, return originale=1, indice
valido e ricontrollato, clip attivo **122**. Nessuna scrittura ad **A65970** o +1E8.
La restrizione caller **2888CC** è stata aggiunta dopo le catture e verificata
dal self-check; è coerente col consumer già osservato nei trace.

**CONFIRMED runtime:** movimento ×1.25, tre secondi per impulso nel corridoio,
direzioni alternate virtual (-0.8660254,-0.5) e inversa. Baseline quattro secondi.
Velocità fisica nei quattro test **12.53–12.56 u/s**, run +1E8 resta 1;
downstream +1D0 diventa esattamente il factor richiesto. Walk resta a 2.0 e
idle escluso. Una prima prova con filtro clip 100122 non ha applicato la
correzione: esclusa e ripetuta dopo verifica dell'ID effettivo 122.

Metodo di calibrazione: stessi clip/contesto, fase `channel+1D4`, ghost XZ.
Somma degli incrementi positivi di fase e della distanza negli stessi intervalli;
esclusi wrap, transizioni clip e gap >0.15 s. Nessuna assunzione sulle unità
della fase o durata del clip. Il rapporto distanza/fase è un proxy di cadenza,
NON una misura del foot sliding. Nessun bone world transform o video analizzato.

| Move | Animation | Phase units/s | World units/phase | Scarto dalla baseline | Collision / stability |
|---:|---:|---:|---:|---:|---|
| 1.00 | 1.00 | 59.715 | 0.167700 | riferimento | corridoio stabile |
| 1.10 | 1.00 | non calibrato qui | non misurato | UNKNOWN | muro: 1 evento 246 su 3 prove |
| 1.20 | — | non testato | non misurato | UNKNOWN | nessun default dedotto |
| 1.25 | 1.10 | 66.558 | 0.195600 | +16.6% | corridoio stabile |
| 1.25 | 1.15 | 68.582 | 0.182280 | +8.7% | corridoio stabile |
| 1.25 | 1.20 | 72.508 | 0.174696 | +4.2% | corridoio stabile |
| 1.25 | 1.25 | 74.639 | 0.167084 | -0.4% | corridoio stabile |

Baseline 52 intervalli utili, factors 38/38/37/37. Errori di fase/posizione possono
derivare dal polling non atomico; nessun intervallo di confidenza stimato.
**HIGH CONFIDENCE:** pairing candidato **1.25 movement / 1.25 animation** conserva
meglio il rapporto distanza/cadenza della baseline. NON è un default approvato:
foot sliding e impressione visiva restano non misurati direttamente.

La moltiplicazione usa dati locali al singolo call, senza accumulatori condivisi
fra worker. Il logger diagnostico condiviso resta non atomico, escluso dalle
promesse di sincronizzazione. Cambio physics ID/owner/controller/channel abortisce
la cattura; un nuovo channel resta originale. Activation byte azzerato al teardown,
vptr ripristinati, codice trattenuto fino all'uscita del processo. Respawn/area
change e distruzione concorrente non sono stati provocati: non è un lifecycle
manager pronto per produzione.

### Final decision and cleanup

**NOT READY. Unico blocker operativo successivo:** isolare il trigger
**246 / 1F625A** al muro, distinguendo input/azione originale da geometria,
confrontandolo nello stesso setup vanilla e moltiplicato. Questo deve spiegare
o rendere riproducibile anche l'escursione storica +12 prima di dichiararla chiusa.
Nessuna specifica READY/config con default di release è emessa.
Sanity aggiuntivo, town/combat e lifecycle restano verifiche subordinate al gate;
non è stata ampliata questa sessione a quelle fasi. L3 finale non implementato.
Binding futuro: Left Shift / L3, Hold/Toggle configurabile nella Phase 1.

**CONFIRMED cleanup:** tutte le catture complete riportano `restored`; ultimo
processo verificato con vptr player **14080AE08**, KCC **140879BD0**, channel
**140822AE8**. Gioco chiuso, pagine diagnostiche terminate col processo;
pad neutralizzato/disconnesso; override FPS eliminato e `fps:null` verificato.
Mod locali nello stato iniziale disabilitato, servizi Special K 32/64 nuovamente
Running. Nessun driver installato, EXE/CPK modificato o capture grezzo incluso.
Self-check run perturbation, walk trace, runtime reader, virtual pad e FPS limiter
passati; compilazione Python e `git diff --check` passati. Commit separato dei
soli quattro file di tool/documentazione, sulla branch corrente `master`.

## TRACE-246-01 — static trigger and diagnostic preparation, 2026-10-02

Questa sezione aggiorna il gate. **NOT READY**: manca ancora il confronto runtime
del medesimo trigger vanilla e **1.25 movement / 1.25 animation** nella lane
definita sopra. Due catture vanilla nella zona attuale verificano la strumentazione
e i campi idle/walk/run; non sono ripetizioni della lane storica.

### Exact branch conditions

**CONFIRMED static:** unwind chaining risolve il parent di `1F6045–1F6296` in
**1F5B30**. RDI è il player, R12D=0, R14=`player+9E10`, XMM9=0.
La funzione salva tre registri e riserva `150h` bytes. Il return del parent,
all'ingresso del setter, è a **entry RSP+170h**; il vecchio offset del normale
caller 206660 NON è valido qui. Il nuovo logger non interpreta quel vecchio
offset fuori dal return 1E993F.

Il percorso fino a `1F6219 / 1F6254` richiede:

1. `field_A021=0`, virtual `+530(2)` vero e mask `0x04` di `field_A047` assente,
   per superare l'entry gate. A021 nonzero usa un altro percorso e non arriva qui.
2. `field_A025 != 0` al controllo `1F5F00`.
3. Il risultato Y della query, in XMM11, è **maggiore** di
   `requested_world.Y + xmm2` al confronto `1F603B`. XMM2 deriva dal calcolo
   verticale `1F6001–1F6026`, con aggiornamento di `field_9F58`.
4. `field_A025 != 0` e `field_9F58 < 0`, controlli `1F6060 / 1F606D`.
5. `field_9FDC * π / 180 > xmm11` al confronto `1F61C4`; qui XMM11 è già
   stato sostituito dal risultato della funzione matematica `1ADC40`.
6. `field_9FF8 < 600`, controllo `1F61D6`.

**HIGH CONFIDENCE static:** `1ADC40` calcola l'angolo con argomenti
`normal.Y` e `sqrt(normal.X²+normal.Z²)`; il confronto è quindi un limite
angolare derivato dalla normale della superficie. Non chiamare questo valore
direttamente inclinazione del terreno senza distinguere l'angolo complementare.
Se XZ della normale è zero il ramo lascia XMM11=1: caso distinto da atan2.

Prima della call, `requested_world.Y` viene portato all'altezza della query
(`1F60C6`). `1AD750` normalizza la componente XZ della normale; il target
passato al setter aggiunge `0.5 * (1-normal.Y)` lungo tale direzione.
Il parametro XMM2 è separatamente **0.5 originale**, caricato a `1F6219`.
Il movimento verticale è quindi richiesto dal gameplay prima di Bullet;
questo ramo non è l'implementazione dello step-up KCC `72AE80`.
I valori KCC +44=0.035/+48=0.02 non sono il limite del target gameplay.

### Fields, writers and query

| Field | Writer statici identificati | Reader pertinenti | Runtime nuovo |
|---|---|---|---|
| `field_A025` | 1F4237=1, 1F43A7=1; 1E1F10=0; 20E4F7=0; 22804E/248BD9 copiano bit 0 di un descrittore +14 | 1F5F00, 1F5F40, 1F6060; getter 1E7530 | idle/walk/run: 0; prima/durante/dopo trigger: UNKNOWN |
| `field_9FDC` | costruttore 1DA691=50.0; 23A923=-15.0 su una classe con altro vtable, non prova di un writer player live | 1E0D30, 1F61AC | idle/walk/run: 50.0; al trigger: UNKNOWN |
| `field_9FF8` | costruttore 1DA676=0; reset 1F5EEC/1F62FC/1F6619/1F6642; incremento 1F6273 | 1F61D6, 1F626B | idle/walk/run: 0; al trigger: UNKNOWN |

Questi sono riferimenti diretti identificati, non un inventario di ogni possibile
scrittura indiretta/bulk. Nomi semantici dei campi volutamente non assegnati.
`69B4C0` restituisce A63240 oppure A63248 moltiplicato per una costante secondo
C82FAC. `field_9FF8` accumula questo valore; **600 non è dichiarato in secondi**.

**CONFIRMED static:** `31EE00` viene chiamata a `1F5CC0` e, se fallisce, a
`1F5D2D` dopo una piccola perturbazione XZ di 0.001. Le due estremità della
query hanno lo stesso XZ: Y iniziale = posizione richiesta Y + max(9FC8,1.2),
Y finale = posizione richiesta Y - 1000. La call `6CB920` riceve gli endpoint;
il risultato restituisce Y da +60 e normale da +80 nello stack della query.
Questi vengono copiati nello stack della locomotion, rispettivamente +50 e
RBP-80. **HIGH CONFIDENCE:** query verticale della superficie, non un test
orizzontale di ostacolo superabile. Se entrambe le query falliscono, esistono
fallback e `field_A04C=2`; il logger lo conserva senza inventare una semantica.

### Why request 246 follows the branch

**CONFIRMED static:** dopo il setter return `1F625A`, la call `1F6260` invoca
virtual **+428 = 20D0C0**. Questo chiama `1F4230`, poi `2C4450` con
`player+A9B8`. Quando `1E59D0` restituisce zero, `2C449E` seleziona stato **4**
tramite virtual +4F0=207AD0 → 1E4840. La tabella dello stato 4 contiene
`206,246,952,956,960,964`; il predicato virtual +448 seleziona 206 oppure 246.
La call **2C44DC → 1DDD70 → player+460** emette la request, con return
**2C44E1** osservabile dal logger. Segue una transizione tramite 169210.

Il predicato +448=1E7F30 è vero quando `field_A01E != 0` e +438=20AD60 è
falso. Nel percorso A03C=0, +438 legge A01E e, se presente, restituisce
`F8A6==0`; con A01E nonzero e F8A6=1 seleziona quindi **246**.
A03C nonzero usa invece 1E7970, confronto di +9F24 con una costante.
Nessun nome definitivo vault/jump/climb è dedotto dal numero dell'animazione.

**CONFIRMED static:** il ramo speciale chiama direttamente il percorso che può
emettere 246 **dopo** la call al setter, nello stesso update. Non è soltanto una
correlazione tra due numeri. +428 è chiamato anche da altri rami, fra cui
1F65E0 e 1F6613: clip 246 da solo non identifica univocamente 1F625A.
L'ordine effettivamente osservato e il caso di transizione differita restano
da verificare col trace runtime.

### Diagnostic contract and current limitation

`walk_trace.py` aggiunge un secondo shim in una pagina privata di **12 KiB**,
raggiunto tramite il tail jump del logger esistente. Solo il return **1F625A**
produce il record mirato. Salva parent caller, player, A025/9FDC/9FF8/9F58,
XMM2, XMM11 angolare, altezza e normale della query, requested world al setter.
Il polling associa tempo monotonic osservato, input consumato, F8/context,
request recente, clip, player/ghost/target/requested XYZ e KCC displacement.
A021/A01E/A03C/A04C sono aggiunti ai campioni ordinari per confrontare gli stati.

Il callsite/predecessore riportato è **ricostruito staticamente**, non una
registrazione dell'instruction stream. Il timestamp è al polling, non al momento
CPU della call. Snapshot di shim, copia KCC e campi letti dal processo non sono
una singola transazione atomica; il logger condiviso conserva il limite di
concorrenza già documentato. Contatore delle call speciali e campioni osservati
sono separati: il polling può perdere call. Flag, registri scratch e argomenti
originali vengono preservati; nessuna patch di 1F6219, clamp Y o soppressione.

**CONFIRMED verifica offline:** self-check e decodifica completa Capstone degli
shim, limite degli slot e target del ramo di esclusione passano. Il tail jump
attraverso il nuovo shim è **live-tested sul percorso di esclusione**; il corpo
che cattura 1F625A non è ancora stato eseguito live. Il pairing 1.25/1.25 resta quello precedente;
nessuna nuova calibrazione né default di release.

Computer Use non ha aperto SKIF (`accessibility window-opened handler did not
become ready`). Il comando nativo documentato `SKIF.exe Stop` ha poi fermato
entrambi i servizi 32/64 senza intervento dell'utente; mod locali disabilitate
con `mods.ps1 off`, cap driver 30 e lancio tramite Steam.
Fonte per Stop/Start: [SKIF command-line arguments](https://github.com/SpecialKO/SKIF#command-line-arguments).

**CONFIRMED runtime, smoke della strumentazione:** il salvataggio attuale carica
**Foresta Grilim**, regione **Foresta di Oldrobe**. Ghost iniziale circa
(-619.990,21.167,-383.600), diverso dal setup storico. I file ignorati
`.cache/trace246-grimm-state-baseline.jsonl` (nome iniziale provvisorio, 30 s)
e `.cache/trace246-grilim-run-baseline.jsonl` (20 s) contengono rispettivamente
450 e 300 campioni di polling. Primo: 387 clip 0 e 63 clip 100; secondo:
253 clip 0, 2 clip 100 e 45 clip 122. Nei campioni A025=0, 9FDC=50,
9FF8=0 e 9F58=0; nessuna call speciale. La seconda cattura include un impulso
virtuale (0,1), 3 s, buttons=0, multiplier 1.00. Entrambe riportano `restored`.
Questi campioni non misurano la frequenza del trigger sulla lane storica.

**UNKNOWN riproducibilità della lane:** il report precedente conserva XYZ,
input/durata e gate, ma non il nome/ID della zona. Le coordinate locali non
identificano una geometria tra aree differenti. La mappa corrente è stata
ispezionata tramite Computer Use; nessun viaggio verso una zona ipotizzata,
nessun confronto 1.25 su una geometria diversa. È stato richiesto il solo nome
della zona storica, senza richiedere guida o input manuale.

**Decisione: NOT READY. Unico blocker:** catturare e confrontare la firma del
trigger geometrico 1F625A/246, vanilla e 1.25/1.25, nella lane già definita;
la relazione statica è identificata, l'equivalenza runtime non è dimostrata.
Prossimo passo preciso: identificare la zona della lane storica, tornarvi tramite
viaggio rapido e applicare il trace già pronto alle ripetizioni 1.00 e 1.25/1.25.
La classificazione A/B/C/D/E resta UNKNOWN. Sanity subordinato non eseguito;
nessuna Sprint implementation o altra fase avviata.

**CONFIRMED cleanup di questa sessione:** dopo le catture, verifica read-only dei
vptr player **14080AE08**, KCC **140879BD0**, channel **140822AE8**. Gioco chiuso
e pagine diagnostiche terminate col processo. Pad terminato tramite il finally
di `virtual_pad.py`, reset/update e disconnect; limiter terminato con
`restored, fps:null`, rimuovendo il cap temporaneo 30. Mod locali **attive**
(d3d11.dll e SAO HR Ultrawide.asi) e servizi Special K 32/64 attivi, come
all'inizio. Il controllo ha individuato un errore di precedenza nell'espressione
`-replace` di `mods.ps1 on`: parentesi aggiunte al pattern concatenato;
ripristino dei due nomi e stato active/disabled verificati dopo la correzione.
Nessun EXE/CPK scritto, driver installato o capture grezzo incluso nel commit.
Self-check walk trace, run perturbation, runtime reader, virtual pad e FPS
limiter, py_compile e `git diff --check` passati.

### TRACE-246-01 — zona identificata dall'utente, accesso ancora da verificare

**CONFIRMED comunicazione dell'utente (2026-10-02):** la lane storica si trova
in **Anticamera delle Grandi Pianure Rastoria**. Questa indicazione supera il
precedente passo di ricerca del nome della zona. Setup da recuperare: ghost
circa **(-7.67, 1.40, 131.39)**, pad **(-0.5, 0.8660254)**, buttons=0,
impulso **4.0 s**, camera non manovrata, direzione world circa -X con piccola +Z.

**CONFIRMED runtime, sola navigazione:** avvio vanilla tramite Steam, mod locali
disabilitate, servizi Special K fermati e cap temporaneo 30. Computer Use e pad
virtuale hanno consentito viaggio in Piazza del teletrasporto, selezione di
**Poggio Phoeniath** nella mappa Rustoria e successivo ritorno in piazza.
Il nome Poggio Phoeniath e la posizione sulla mappa sono stati verificati nella
UI; non dimostrano accesso all'Anticamera. I nodi ispezionati non hanno mostrato
quel nome. Una porta nella piazza è risultata inaccessibile, senza cambio area.
Questo non esclude altri ingressi o collegamenti. È stato richiesto il solo
percorso di accesso, senza richiedere movimento manuale per le prove.

**UNKNOWN:** accesso e verifica visiva/XYZ della lane. In questa ripresa non sono
stati installati hook né eseguite nuove catture comparative: nessuna evidenza
aggiuntiva sul trigger `1F625A/246`, nessuna classificazione causale e nessun
sanity subordinato. La navigazione non conta come test collisione.

**Decisione invariata: NOT READY. Unico blocker:** confronto runtime del trigger
`1F625A/246` sulla lane storica verificata, con ripetizioni vanilla 1.00/1.00 e
1.25/1.25. Prossimo passo: verificare il collegamento all'Anticamera, raggiungere
la lane col pad virtuale e applicare il trace esistente. Nessuna implementazione
Sprint o altra fase avviata.

**Cleanup:** gioco chiuso; nessun hook/vptr modificato durante questa ripresa.
Pad terminato tramite il finally di `virtual_pad.py`; limiter terminato con
`restored, fps:null`. Stato finale verificato: d3d11.dll e SAO HR Ultrawide.asi
attivi, nessun file disabilitato, SKIFsvc32/SKIFsvc64 attivi e processo gioco
assente. Self-check walk trace, run perturbation, virtual pad, FPS limiter e
runtime reader passati; `git diff --check` passato. Nessun EXE/CPK modificato.

### TRACE-246-01 — Anticamera, collisione riprodotta (2026-10-07)

**Decisione: NOT READY. Unico blocker: COLLISION-SLOPE-01**, ascesa nel percorso
ordinario lungo il muro inclinato. L'accesso alla zona e il corpo del trace 246
sono ora verificati; questa sezione supera le conclusioni operative precedenti.

#### Setup e limiti

**CONFIRMED runtime:** Piazza del teletrasporto -> mappa Rustoria -> nodo castello
con destinazione UI **Anticamera**, teletrasporto diretto sbloccato. Nessun bisogno
di attraversare Arktarium 1F/2F o aprire una barriera. Ghost all'arrivo circa
(36.129,1.849,178.775). Pad virtuale e letture XYZ raggiungono il muro/lastra
inclinata vicino allo start storico. Quota iniziale 1.40; impulso **4.0 s**,
pad **(-0.5,0.8660254)**, buttons=0, camera non manovrata; input consumato
**(-65,-111)**, direzione world quasi -X con piccola +Z. Cap driver richiesto
30 prima dell'avvio Steam, senza nuova verifica esterna del render FPS;
poll dt ~0.067 s. Nessuna scrittura di posizione, reset solo con input inverso.

**Reset non bit-identici:** vanilla `100-4` parte da (-7.894,1.400,131.640);
`125-2/3/4` da (-7.912/-7.958/-7.931,1.400,131.638/131.635/131.639).
In questo sottoinsieme errore start X <=0.065 e Z <=0.006, stesso muro/input.
Z resta circa 0.25 sopra lo storico 131.39. Le altre prove comparabili partono
da X -8.10..-7.18, Z 131.535..131.640, salvo la prima baseline
(-6.465,1.400,131.310). Le traiettorie reali divergono al contatto; non chiamarle
identiche. Yaw/camera non letti in memoria: direzione/input documentano
l'allineamento senza inventare un valore yaw esatto.

#### Baseline corrente e esclusioni

**CONFIRMED:** walk=0.0434300005, run=**0.1693770140**, bits **3E2D712B**,
FF/FE, F8A6 e caller ordinario verificati. Rapporto ~1.01 rispetto alla baseline
storica; causa del fattore aggiuntivo **UNKNOWN**. Non riscrive 3E2BB98D storico.
`run_perturb.py --baseline-bits` accetta solo questi due valori osservati,
default storico invariato; confronto esatto in entrambi gli shim, altri filtri
invariati, valore originale moltiplicato. Self-check prima del live, nessun
apprendimento automatico o allargamento del guard.

Captures ignorati `.cache/trace246-rastoria-<factor>-<run>.jsonl`:

- `100-1`: trace terminato prima dell'impulso, zero movimento, scartato.
- `125-1`: richiesta 1.25/1.25 esclusa dal guard storico; parametro/rate vanilla,
  non conta come prova Sprint effettiva.
- `115-3`: start (-12.260,1.400,131.624) dopo l'evento precedente; osservazione
  accessoria stabile, esclusa dalle ripetizioni comparabili.
- `100-7`: cambio contesto, clip 100000/101152, request 1152, caller 1F54E4;
  esclusa dalla baseline exploration/run. Il tentativo successivo `115-4` termina
  senza output `logging` o cattura valida; stderr non conservato, non conta come test.

#### Collisione e boundary

| Move / animation | Prove comparabili | Ghost Ymax per prova | Call 1F625A | Valutazione |
|---|---|---|---|---|
| 1.00 / 1.00 | `100-2..6`, 5 | 1.5970, 1.5938, 1.5953, 1.5955, 1.5964 | 0 | Controlli stabili |
| 1.10 / 1.10 | `110-1..3`, 3 | 1.6132, **11.6899**, 1.6132 | 0 | Ascesa ordinaria intermittente |
| 1.15 / 1.15 | `115-1..2`, 2 | 1.6240, **14.2178** | 0 | Ascesa ordinaria, +12.82 Y |
| 1.20 / 1.20 | `120-1..3`, 3 | 1.6343, 1.6319, 1.6356 | 0 | Stabile nella piccola serie, soglia sicura non provata |
| 1.25 / 1.25 | `125-2..4`, 3 | 1.8493, **4.7948**, **3.1188** | 0, 0, **11** | Ascesa ordinaria e azione speciale distinte |

Run effettivo: 1.10=0.186314717, 1.15=0.194783568, 1.20=0.203252420,
1.25=0.211721271; playback run perturbato al rispettivo fattore.
Detector `suspect_vertical`: 56 campioni `110-2`, 132 `115-2`, 25 `125-3`,
8 `125-4`; zero nei controlli vanilla validi. Poll sequenziali, non frame atomici;
conteggio dei campioni sospetti non è frequenza degli eventi CPU.
Grande +12 Y riprodotto come fenomeno, **non** nelle condizioni esatte del vecchio
test 1.25. Risposta non monotona: tre prove 1.20 stabili non danno un default sicuro.
Movement e animation variano insieme in questa serie: non separa l'effetto dei
due hook, né esclude un contributo del playback alla submission ordinaria.

**CONFIRMED runtime:** `110-2`, `115-2`, `125-3` ascendono con caller
**1E993F**, clip/request **122**, A025=0, A021=0, A01E=1, A03C=0, A04C=1,
9FDC=50, 9FF8=0, zero call speciali. 9F58 negativo in `110-2` (-0.432666)
e `115-2` (-0.154300), ma A025 resta zero. Ghost/player Y aumentano insieme,
offset ~1.40: non è solo un artefatto del campo player. Target X ordinario ~100
unità oltre il player non prova da solo attraversamento della geometria.

**HIGH CONFIDENCE:** l'ascesa segue la superficie inclinata. Nei campioni in
salita con 2<Y<13 e deltaX negativo, mediana deltaY/-deltaX:
`110-2` **3.656299** (41), `115-2` **3.656283** (36), `125-3` **3.656224**
(30). La normale della query speciale nello stesso muro dà Nx/Ny=**3.656245**.
In 8/41 campioni `110-2` e 14/30 `125-3`, displacement KCC richiesto Y negativo
e delta ghost positivo sono compatibili con correzione verticale al contatto,
con il limite temporale del polling. Step fields 0/0.035/0.02, contact flags
1/0/1/0, ground fields 0/0; `on_ground` diagnostico non prova un appoggio valido.
**UNKNOWN:** quale ramo KCC/aggiornamento target consenta la risalita;
non dimostrati tunneling o penetration recovery.

#### Firma 1F625A/246

**CONFIRMED runtime `125-4`:** 11 call e 11 record osservati, parent caller
**1F5271**, setter return **1F625A**, callsite statico 1F6254. Primo record:

| Campo | Valore |
|---|---|
| A025 / A021 / A01E / A03C / A04C nel poll associato | 1 / 0 / 1 / 0 / 1 |
| 9F58 al setter | -0.031180203 |
| 9FDC / 9FF8 | 50 / 0; 9FF8 fino a 16.025543 nei record osservati |
| Surface query Y | 1.773118377 |
| Surface normal | (0.964573264,0.263815254,0.000096804) |
| XMM11 angolare | 0.266975462 rad, inferiore a 50*pi/180 |
| XMM2 originale | **0.5 in tutti gli 11 record** |
| Requested world al setter | (-19.410387,1.773118,131.547394) |
| Target nel poll associato | (-19.042295,1.773118,131.547424) |
| Ghost / player Y nel poll associato | 2.866334 / 1.466334 |
| KCC displacement associato | (-0.550432,0.717651,0.003372) |
| Request / clip / downstream rate associati | **246 / 246 / 1.0** |

I 21 campioni con clip 246 hanno rate 1.0. Entrambe le perturbazioni escludono
questo percorso. Alcuni record speciali si associano a poll ancora ordinari/rate
1.25: logger/poll non atomici, non prova di modifica della clip 246.
Corpo del trace ora live-tested, oltre al percorso di esclusione già verificato.

**Classificazione:** 1F625A/246 è **CONFIRMED percorso originale**, query e
condizione angolare coerenti con l'analisi statica, parametro preservato.
Sprint ne favorisce l'ingresso: **PROBABLE**, 1/3 prove effettive 1.25 contro
0/5 controlli vanilla; reset e numerosità non danno causalità definitiva.
Amplificazione diretta del parametro/playback esclusa nei dati osservati.
Le tre grandi ascese ordinarie sono **non correlate all'esecuzione di 246**:
non si può chiudere ogni collision regression come normale special movement.

#### Animation relationship e readiness

Case B e il precedente proxy distanza/fase favorevole a 1.25/1.25 rimangono
validi nel loro contesto. Nuova verifica dell'esclusione live di clip 246;
nessuna nuova misura foot sliding, cadence o contatto piede/terreno sul piano.
Il muro non è una lane di calibrazione del passo. Nessun bone RE o video nuovo.
Nessuna coppia promossa a default. Sanity di altre geometrie, town/combat e
lifecycle subordinati al gate collisione fallito, non blocker aggiuntivi.

**NOT READY — unico prossimo blocker, COLLISION-SLOPE-01:** localizzare la
correzione verticale del percorso ordinario sulla lastra tramite pre/post KCC
sincronizzati al contatto, separando movement-only dal pairing animato, e
dimostrare un comportamento Sprint che non risalga
il muro nelle ripetizioni comparate. Riutilizzare area/input/serie; abbassare
soltanto il multiplier o attribuire tutto a 246 non risolve i dati osservati.
Nessuna specifica/default di release pronta. Futuro input: Left Shift / L3,
Hold/Toggle configurabile, non implementato. Nessuna fase Audio o altra fase.

**CONFIRMED cleanup:** tutte le 20 catture concluse riportano `restored`.
Vptr letti prima di chiudere: player 14080AE08, KCC 140879BD0, channel 140822AE8.
Gioco poi assente, pagine diagnostiche terminate; pad terminato tramite finally
(reset/update, disconnect); limiter tramite finally, `restored, fps:null`.
d3d11.dll e SAO HR Ultrawide.asi attivi, nessun file disabilitato,
SKIFsvc32/SKIFsvc64 attivi come all'inizio. Nessuna patch EXE/CPK,
installazione driver o capture grezzo versionato. Self-check run perturbation e
walk trace, py_compile del tool modificato e `git diff --check` passati.

### COLLISION-SLOPE-01 — 2026-10-09

#### Synchronized KCC trace

**CONFIRMED runtime:** `tools/slope_trace.py` registra sei snapshot nello
stesso update del KCC del player: prima/dopo wrapper `58D340`, preStep
`72A160` e playerStep `729EF0`. I callback della sola istanza, slot +60
`5875A0`, condividono sequence/thread con l'update. Originali e argomenti
preservati; nessuna scrittura a ghost, richiesta Y, step height o collisioni.
Campi: ghost/current/target, richiesta +50, direzione +60, stato +20..4F,
C0..CF, normale D0, E0..EF, normale/punto del contatto e current/target prima
e dopo callback. Schema 2 aggiunge hit fraction del caller forward `72ADDB`
e stato del latch diagnostico prima/dopo update.

La ring è limitata a 4096 update e sette callback/update; pubblicazione a
fine update, conflitti di contesto e overflow invalidano la cattura. I poll
player/query/animation restano sequenziali, non atomici con questi snapshot.
Sequence identifica un update, non un frame video; tempo monotonic disponibile
nei poll e nei log del pad, non in ogni snapshot. Osservati due update KCC
per submission, con E3 alternato: non contarli come due frame indipendenti.

#### Separazione movement / animation

Anticamera, camera non manovrata nella serie, input virtuale
`(-0.5,0.8660254)`, buttons=0, impulso 4 s. Cap NVIDIA richiesto 30 prima
del riavvio: questa nuova serie non aggiunge una misura FPS esterna.
Poll dt ~0.0667 s e scalar wrapper ~0.0166667, coerenti con la serie storica.
Reset tramite pad, non scritture di posizione: riportare gli start esatti,
non assumere prove bit-identiche. Detector: ghost Y>2 nella lane bassa,
oppure abs(deltaY)>0.10 per update; le normali piccole correzioni di contatto
possono superare il secondo criterio, che da solo non prova regressione.

| Move / animation | Capture locali | Start X (Z≈131.64, Y=1.40) | Max ghost Y | Risultato |
|---|---|---|---|---|
| 1.00 / 1.25, animation-only | `slope-30-A1..3` | -7.772, -7.814, -7.831 | 1.5950, 1.5952, 1.5950 | Nessuna grande ascesa |
| 1.25 / 1.00, movement-only | `slope-30-B1..3` | -7.772, -7.790, -7.830 | 1.6466, 1.6410, 1.6417 | Nessuna grande ascesa |
| 1.25 / 1.25, combined | `slope-30-C1..3` | -7.779, -7.803, -7.811 | 1.6412, 1.6411, 1.6414 | Nessuna grande ascesa |
| 1.00 / 1.00, vanilla | `slope-30-D1..3` | -7.737, -7.778, -7.826 | 1.5956, 1.5947, 1.5945 | Nessuna grande ascesa; D1 Z=131.606 |
| 1.15 / 1.15 | `slope-30-115-near-old` | -7.296160, Z=131.641861 | **5.3738** | Ascesa ordinaria riprodotta |
| 1.15 / 1.00, movement-only | `slope-30-115-move-only-2` | -7.407774, Z=131.637878 | **14.2178** | Ascesa ordinaria riprodotta |

Tutte queste catture: zero special calls, zero conflitti/overflow/callback
overflow, ripristino registrato. Run speed effettivo 1.15=0.194783568;
rate run 1.15 nel pairing e 1.0 nel movement-only. Le prove a cap 60
`slope-A/B/C/D*` senza grande ascesa non sostituiscono quelle a cap 30.
`slope-30-115-move-only-1` è esclusa: nessun impulso efficace.

**CONFIRMED:** il playback accelerato non è necessario all'ascesa.
**UNKNOWN:** animation-only non dimostrato innocuo per ogni start; tre prove
stabili non danno tale garanzia. Anche 1.25 stabile in questa serie non annulla
le precedenti ascese ordinarie a 1.10/1.15/1.25. Nessuna soglia sicura scelta.

#### Collision normal relationship e primo delta Y

**CONFIRMED static + runtime:** il forward step `72A9D0` chiama `72B3C0`
dal callsite `72ACC8`, prima del callback `72ADDB`. La routine proietta
il displacement sulla superficie. Con normale unitaria e fattore XMM3=1:

`v_projected = v - dot(v, normal) * normal`

L'implementazione normalizza/riflette il vettore, toglie la componente normale
e riapplica la lunghezza. Non contiene una divisione esplicita per Ny.
Target Y viene scritto in `72B5EA`; la componente proiettata Y è calcolata
in `72B597`. Il rapporto osservato dY/-dX≈3.656 nasce dalla geometria della
normale, non da un moltiplicatore verticale introdotto dal nostro hook.

Record **337** di `slope-30-115-near-old`, nello stesso update:

| Campo | Valore |
|---|---|
| Ghost prima | (-18.486170, **1.408951**, 131.503342) |
| Richiesta KCC +50 | (-0.589489, **-0.000034981**, 0.003631592) |
| Normale forward | (0.964566469,0.263840288,0.000127155) |
| dot(v,n) | -0.568610190 |
| Current al callback | (-18.486170, **1.443951**, 131.503342) |
| Target al callback | (-18.527197, **1.593939**, 131.507050) |
| Ghost dopo | (-18.527197, **1.558939**, 131.507050) |

La formula ricostruisce il target entro l'arrotondamento float. La richiesta
Y è negativa, ma il delta ghost finale è **+0.149987**. preStep non sposta
il ghost; callback originale non cambia current/target. L'up step introduce
0.035, poi il down step lo sottrae: il rialzo netto è già nel target proiettato.
La pubblicazione del ghost è nel playerStep, `72A139`.

**CONFIRMED:** nei due trace di grande ascesa, tutti gli update con Y>2 hanno
delta ghost preStep zero; i callback non alterano current/target. Non è il
penetration recovery del preStep a produrre questi rialzi. Non dedurre che
non esista mai recovery o tunneling altrove: questo trace non misura ogni
profondità di contatto e non dimostra attraversamento della mesh.

Il movement-only mostra anche una seconda situazione: sequence **335** entra
già con richiesta Y **+0.286139** e la proiezione porta il rialzo netto a
**+0.375056**. Quindi il primo Y positivo non nasce sempre dentro Bullet.
**PROBABLE:** feedback del target ordinario/terreno una volta raggiunta la
lastra; writer upstream esatto non localizzato in questa sessione.
Zero 246 in entrambe le catture: questo meccanismo è distinto dall'azione
speciale già esclusa. Classificazione: **risposta originale KCC amplificata
dal displacement Sprint**, con accesso alla superficie sensibile allo start;
non una nuova patch verticale o una regressione dimostrata del playback.

#### Fix candidate e validation

Prova diagnostica `--suppress-on-contact`: al primo callback forward
`72ADDB` con +9F24 pari al run perturbato, latch atomico player-only. I
successivi getter movement/rate saltano i moltiplicatori; la risposta fisica
originale rimane intatta. Reset previsto solo a richiesta KCC XYZ nulla.
Il callback avviene **dopo** la proiezione: candidato conservativo, non fix
approvato. Non installare questa logica come Sprint production.

**CONFIRMED runtime, `slope-fallback-115-1`, 2026-10-09:** move/animation
1.15/1.15, start **(-8.124241,1.400000,131.625809)**. È la stessa geometria,
ma start X diverso dalle precedenti prove: non un confronto appaiato.
Impulso pad 4 s; finestra trace 20 s copre circa i primi 3 s del movimento,
non il rilascio completo. 600 update, nessun conflitto/overflow, restore riuscito.

- Primo latch, sequence **541**: ghost Y **1.407321 → 1.716587**;
  richiesta Y già **+0.209700**, normale (0.964572966,0.263816118,0.000127158),
  hit fraction **0.104247**. preStep e callback non modificano le posizioni.
- Stato latch: 540 update false/false, uno false/true, 59 true/true;
  **52 update già soppressi con Y>2**, max Y **4.656038**, max deltaY **0.309267**.
- Poll successivo al latch: +9F24 **0.169377014**, downstream rate **1.0**,
  Y **1.818106**. Prima: speed **0.194783568**, getter run **1.15**.
  Rate 2.0 resta quello originale del walk. Nessuna special call.

**Esito: FAIL.** Il latch funziona, ma non elimina l'ascesa una volta iniziata.
Non serve una seconda prova per respingere una garanzia di sicurezza già
contraddetta. Il tentativo `slope-fallback-125-1` è escluso: guard FF/FE
fallita prima dell'installazione, dopo variazione del contesto/input;
nessun risultato multiplier valido. Reset del latch al rilascio e lifecycle
non verificati live in questa prova troncata.

#### Final readiness

**NOT READY. Unico prossimo blocker:** verificare un filtro **prima della
submission ordinaria ascendente** che sopprima entrambi i moltiplicatori
sulla lastra, e dimostrare in confronti ripetuti che non consenta la risalita
extra rispetto a vanilla. Il callback dopo la proiezione è troppo tardi;
ridurre arbitrariamente a 1.20 non sostituisce la verifica.

Causa fisica localizzata e movement-only positivo; resta la prevenzione.
Sanity altre geometrie/town/combat/lifecycle rimane subordinato a questo gate,
non è una lista di nuovi blocker. Calibrazione precedente distanza/fase
conservata, foot sliding diretto non misurato. Nessun default o specifica
implementativa di release approvata; Left Shift/L3, Hold/Toggle restano futuri.
Nessuna implementazione Sprint, Audio o altre fasi.

**CONFIRMED cleanup 2026-10-09:** vptr originali riverificati prima dell'uscita
(player 14080AE08, KCC 140879BD0, channel 140822AE8); gioco poi assente,
pagine private terminate. Pad uscito tramite finally, reset/disconnect;
limiter uscito con `restored, fps:null`. d3d11.dll e SAO HR Ultrawide.asi
attivi, nessun file disabilitato; SKIFsvc32/SKIFsvc64 nuovamente attivi.
Nessuna patch EXE/CPK o nuovo driver. Capture locali esclusi da Git.

Self-check `slope_trace`, `run_perturb`, `walk_trace`, py_compile dei tre tool,
parse TOML e `git diff --check` passati. SHA-256 EXE invariata; firma corta
`72B3C0` verificata al suo RVA e unica nel file della build.
Commit firmato ritentato senza bypass:
`git commit -m 'test: 🔬 trace Rastoria slope ascents and Sprint gate' -m 'Co-authored-by: GPT-6 <noreply@openai.com>'`.
Fallito con `error: 1Password: failed to fill whole buffer` e
`fatal: failed to write commit object`. Staging precedente preservato;
nuovo lavoro separato nel working tree, incluso `tools/slope_trace.py`.

## COLLISION-SLOPE-02 — 2026-10-09

### Original slope predicate and earliest hit information

**CONFIRMED static:** setter `72A570` salva l'angolo in KCC `+34`, chiama
`6EAB98` (import `cosf`) e salva il risultato in `+38`. `stepDown` carica
questo coseno a `72A7E1`. Il closest callback `729CB0`, a `729DA5/729DA8`,
rifiuta quando `threshold > dot(up, world_normal)`; l'uguaglianza è accettata.
La sweep forward usa invece threshold zero. Non confondere questa soglia
con `+9FDC=50`, che appartiene alla special action originale.

**CONFIRMED runtime:** up-axis `+E8=1` (Y), angle `0.0182770453393`, cosine
`0.999832987785`. La normale storica `Ny≈0.2638` è non walkable secondo
questo criterio. Non è stata sostituita con una soglia convenzionale in gradi.
Flat normal e normale di una rampa ordinaria non sono misure nuove consolidate:
il confronto runtime fra tutte le geometrie resta non eseguito dopo lo stop.

**CONFIRMED static:** il nuovo hit è disponibile al return query `72AC99`;
la frazione viene confrontata con 1 a `72ACAD`. Prima di `72ACC8 -> 72B3C0`
sono disponibili normale, hit object, fraction e target/current. Il recovery
precedente `72AB3C` usa invece la normale cached KCC `+D0` quando `+C0!=0`
e il dot con la direzione normalizzata è positivo. Non è un nuovo sweep hit.

### Pre-projection filter, vectors and latch

`tools/pre_projection.py`, usato da `slope_trace.py --pre-projection`, crea
copie private rilocate di playerStep/forward. Solo la vtable dell'istanza KCC
verificata le chiama; codice immagine e proiezione originale restano intatti.
Il gate intercetta solo il logical callsite `72ACC8`, non `72AB3C`.
Filtri: player/KCC/ID fisico della sessione, FF/FE, F8A6=1/F8AD=0,
owner/controller/channel corrente e descriptor clip 122. Nessun fattore globale.
L'ID è risolto nuovamente dopo il riavvio (8 in questa sessione), non fisso a 10.

Con hit valido, `normal.Y < native_cosine` e `dot(incoming,normal)<0`,
il gate attiva il latch e, solo se `+9F24` contiene il run value boosted,
divide `target-current` per il multiplier una volta per physics update.
La proiezione originale riceve quel target. Producer e animation getter usano
il latch per sopprimere i multiplier futuri. Un forward pass senza contatto
qualificante lo rilascia; non occorre attendere un vettore zero o un timer.
Questo rilascio non considera il recovery cached: è un limite del candidato.

**HIGH CONFIDENCE, dati flat riutilizzati:** nel tratto `-10<X<-8.8`, Y=1.4,
12 campioni vanilla/1.15/1.25 hanno `vector.Y=0` e
`vector.X / producer_dt / multiplier = -10.1624334..-10.1624244`.
Z normalizzato varia `0.0624586..0.0625977`, compatibile con cancellazione
float del target world. Questo sostiene la divisione sul piano; non dimostra
che la Y già prodotta dal terreno sia tutta un contributo Sprint lineare.
La vanilla equivalente è ricostruita, non un vettore originale preservato
atomico nello stesso update. L'extra è incoming meno tale ricostruzione.

I record collegano sequence/thread/KCC, current/target, normale/object/fraction,
incoming/vanilla equivalente/extra/passed/projected, native cosine/dot,
run value, eligibility, applied e latch. `passed` nelle prove 1.25 include
l'arrotondamento target-current dopo lo store; nelle prove 1.15 è il quotient
prima di tale arrotondamento. Ghost/preStep/playerStep condividono il sequence.
Poll producer/input/playback e tempo monotonic sono osservazioni separate,
non una snapshot atomica con il thread fisico. Conflitti/overflow invalidano
la cattura. Copie private senza unwind registration: diagnostica bounded,
non un design di produzione o una validazione generale di concorrenza/lifecycle.

### Rastoria validation

Anticamera, stessa lastra verificata visivamente. Camera e right stick non
manovrati; input virtuale `(-0.5,0.8660254)`, buttons 0, impulso 4.0 s;
assi consumati `(-65,-111)`, direzione circa -X con piccola +Z.
Cap richiesto 30 prima del riavvio Steam, senza nuova verifica FPS esterna.
Baseline bits `3E2D712B`. Reset tramite pad inverso, senza teleport/memory writes:
gli start sono bounded, non identici. Ogni cattura completa dura 30 s.

| Capture locale | Move/animation | Ghost start XYZ | Max ghost Y | Deboost events |
|---|---|---|---|---|
| preproj-vanilla-02 | 1/1 | -7.177174, 1.400000, 131.747375 | 1.595798 | 0 |
| preproj-115-01 | 1.15/1 | -7.693682, 1.400000, 131.640152 | 1.604610 | 3 |
| preproj-vanilla-03 | 1/1 | -7.310448, 1.400000, 131.632523 | 1.593651 | 0 |
| preproj-115-02 | 1.15/1 | -7.349705, 1.400000, 131.632217 | 1.595754 | 2 |
| preproj-vanilla-04 | 1/1 | -7.238592, 1.400000, 131.640228 | 1.596203 | 0 |
| preproj-115-03 | 1.15/1 | -7.249524, 1.400000, 131.641937 | 1.595841 | 2 |
| preproj-125-01 | 1.25/1.25 | -7.084576, 1.400000, 131.642502 | 1.596424 | 2 |
| preproj-vanilla-05 | 1/1 | -7.574902, 1.400000, 131.640060 | 1.596197 | 0 |
| preproj-125-02 | 1.25/1.25 | -6.857341, 1.400000, 131.642487 | **12.982490** | 11 |

**CONFIRMED runtime:** tre prove 1.15 stabili, prima 1.25 stabile, seconda
1.25 fallita. Tutte `restored`, overflow/conflicts zero, special calls zero.
Animation 1.25 osservata fuori latch e 1 durante soppressione; walk 2 preservato.
Non si deduce un default sicuro 1.15 da queste sole tre prove.
Controllo vanilla-02 precede la correzione del filtro ID: stessa copia originale,
nessun deboost, eligibility false. I successivi controlli vanilla registrano
eligibility vera e non modificano target/latch. Vanilla-01 è esclusa: pad
riconnesso non consumato, zero movimento. Due setup allocation falliti prima
degli hook sono esclusi; near code e ring ora allocati separatamente.

### First bad update and stop

**CONFIRMED runtime, preproj-125-02 sequence 481, thread 50540:** detector
`abs(deltaY)>0.2` scatta con ghost Y `1.413463235 -> 1.844524145`
(delta `+0.431060910`). Al sequence 483 Y supera 2.0. Requested displacement
KCC `+50` è già `(-0.387470275, +0.355826199, +0.002380371)`.
preStep corregge ghost a `(-18.611001968,1.414867520,131.490646362)`;
playerStep lo porta a `(-18.728504181,1.844524145,131.493072510)`.
Il delta playerStep è `(-0.117502213,+0.429656625,+0.002426147)`.
Latch before/after **false/false**, `applied=false` perché nessun evento
`72ACC8` né callback forward è registrato in questo update.

KCC cached `+D0` prima del playerStep:
`(-0.964579582,-0.263792157,-0.000155674)`; `+C0=1`.
**HIGH CONFIDENCE:** il ramo recovery originale `72AB3C` è il percorso
sfuggito al filtro. Con requested e cached normal letti, il dot vale
`+0.279881385`; la proiezione calcolata produce
`(-0.117502406,+0.429656713,+0.002423941)`, coincidente entro float con
il delta playerStep. È una derivazione sostenuta dal ramo statico e dal delta,
non una chiamata recovery osservata direttamente dal nuovo shim.
La hit fraction e gli esatti target interno prima/dopo recovery sono **UNKNOWN**
in quell'update; la fraction di un nuovo hit non va attribuita alla recovery.
Vanilla-equivalent/extra non sono stati calcolati/applicati dal gate in seq481.
La richiesta animation osservata a elapsed monotonic 15.199551 s è 122/rate 1;
la successiva è idle 0 a 19.196622 s. Clip 122 nel primo update anomalo è
**HIGH CONFIDENCE**, non una lettura channel atomica del seq481.
Ultimo nuovo hit precedente: seq463, fraction 0.500332475, deboost applicato,
latch false->true. Il rilascio successivo ha consentito nuova produzione boosted.

Quindi non è dimostrato che un vettore già riportato a vanilla nel primo update
anomalo continui a salire: **il gate non copre quell'update**. Il requested Y
già positivo rende inoltre insufficiente una giustificazione basata sul solo
scaling flat. Non aggiunte projection alternative, clamp Y, gravity o ghost writes.

### Flat/slope/wall controls and readiness

**NOT READY. Unico blocker successivo:** prevenire l'ascesa ordinaria anche
quando entra il recovery cached `72AB3C` senza nuovo hit `72ACC8`, preservando
il contributo vanilla prima della produzione di requested Y positivo.
Riconsiderare il punto `1E9980` e la correlazione con il target originale nella
prossima sessione; non approvare l'attuale latch come soluzione di release.

STOP dopo il fallimento, come richiesto: nessuna terza prova 1.25, nuovi
flat/ramp/wall obliquo/parallel/away, town/combat/lifecycle o implementazione
Sprint. I controlli non eseguiti restano subordinati al medesimo gate.
Nessuna nuova calibrazione animation, test FPS, TRACE-246 o Audio.

### Cleanup and Git

**CONFIRMED cleanup:** prima dell'uscita, vptr player/KCC/channel originali
`14080AE08 / 140879BD0 / 140822AE8`; gioco chiuso, pagine private terminate.
Pad reset/disconnect via finally; limiter `restored, fps:null`.
Mod locali originali ripristinati e Special K injection riavviata.
SKIFsvc32/SKIFsvc64 attivi e nessun processo sao_hr al controllo finale.
Nessuna patch permanente EXE/CPK, nuovi driver o capture commessi.
Self-check `pre_projection`, `slope_trace`, `run_perturb`, `walk_trace`,
py_compile dei quattro tool, parse TOML e `git diff --check` passati.
Signature corta setter `72A570` unica e al RVA previsto; SHA-256 EXE invariata.

Il retry del commit precedente è riuscito prima di questo nuovo lavoro:
`3465c26 test: 🔬 trace Rastoria slope ascents and Sprint gate`, con firma SSH.
L'errore 1Password riportato in SLOPE-01 è storico. Nuovo lavoro diagnostico
SLOPE-01/02 mantenuto nel working tree, separato dal commit precedente.

## COLLISION-SLOPE-03 — 2026-10-09

### Decision

**NOT READY. Candidato cached suppression respinto alla prima prova.**
**Unico blocker successivo:** individuare un punto di applicazione Sprint che
preservi il percorso vanilla di query terreno/primo contatto, prima che
l'arrivo accelerato sulla lastra produca uno stato KCC e target già divergenti.
Riportare soltanto il parametro `1E9980` a vanilla dopo quel contatto non basta.
Non approvata una state machine production né una patch del recovery.

### Native cached recovery and lifecycle

**CONFIRMED static, `72A160`:** `72A1A0` azzera `KCC+C0` a ogni `preStep`.
La scansione dei contatti considera distanze negative; conserva la normale
del contatto più penetrante del pass a `+D0` (`72A36C`). Il segno dipende
dall'identità del ghost nel manifold: i due fattori sono `+1/-1`, non il
segno di Y. Per i contatti penetranti somma a `current+70` una correzione
proporzionale a normale firmata e distanza negativa. `72A440` pone `+C0=1`
se il pass ha corretto una penetrazione. Ci sono fino a cinque pass; un pass
successivo senza penetrazione non cancella il flag già posto a 1.
La posizione ghost viene aggiornata; al termine current/target sono riallineati
al ghost. `+D0` non viene azzerato quando `+C0` si azzera.

Quindi `+C0` significa operativamente **penetrazione corretta in questo
preStep**, non on-ground, presenza di un nuovo sweep o memoria persistente
di ogni superficie pericolosa. Può restare visibile al producer fra gli update,
ma torna zero al prossimo preStep se non serve una correzione. Il cached
normal non basta da solo a qualificare un contatto ancora attivo.

**CONFIRMED static, `72A9D0`:** target `+90` riceve current più displacement.
`72AAF9` richiede `+C0!=0`. `72AB09..72AB2A` calcola il dot fra **direction
normalizzata `+60`** e cached normal `+D0`; `72AB2E/72AB32` salta se il dot
è `<=0` oppure unordered. Per dot positivo `72AB3C` chiama l'originale
`72B3C0` con `RDX=&D0`, `XMM2=0`, `XMM3=1`, modificando il target `+90`.
Non esiste una nuova hit fraction da attribuire a questa chiamata.

La normale cached firmata punta **dentro** la superficie: la correzione con
distanza negativa sposta fuori. Il ramo originale interpreta quindi dot
positivo come movimento dentro la superficie. Allontanarsi inverte il dot e
salta il ramo. La classificazione walkable del cached normal usa l'orientamento
opposto, `-normal.Y`, contro il cosine nativo; non va copiato il segno del
nuovo hit forward. Il comportamento away è dimostrato staticamente; il sanity
runtime di rilascio non è approvato perché il candidato fallisce prima.

### Direct trace and original producer input

`slope_trace --pre-projection --cached-recovery` aggiunge uno shim sul solo
call site `72AB3C` della copia privata del forward. La chiamata/proiezione
originale è preservata. Nessuna scrittura su C0/D0, normal, ghost o immagine
EXE. Il record recovery contiene sequence/thread del physical update,
current/target prima e dopo, requested `+50`, direction `+60`, C0/D0, dot,
ghost prima/dopo playerStep e snapshot gameplay current/target/integrated/request.
Il ghost after è correlato solo se sequence/thread/completion del record
physical coincidono. I ring sono bounded e overflow/conflicts invalidano la prova.

Il prefix del setter conserva **prima della perturbazione** parametro XMM2,
target in ingresso e current, oltre ai valori preesistenti 9E20/9DF0/9E10.
Il producer ha una propria sequence di pubblicazione; la latest sequence
nel recovery è una correlazione cross-thread, non un frame gameplay atomico.
Le coordinate e il parametro concordano nei record citati sotto.
Non sono stati eseguiti due integrator alternativi: il campo integrated al
producer è lo stato già presente, **non un displacement vanilla controfattuale**.
Anche il target in ingresso è comune a vanilla/boost prima della query;
non è il target terreno originale da riusare dopo una query diversa.

**CONFIRMED runtime, `cached-trace-125-02`, seq299/thread20128:**
recovery osservato con `C0=1`, latch false, parametro boosted `0.211721271`.
Requested `(-0.405292541,+0.322403222,-0.000228882)`;
normal `(-0.964578271,-0.263796896,-0.000097704)`;
dot requested/normal `+0.305887431`.
Current prima della proiezione `(-18.608367920,1.447212100,131.376174927)`;
target prima `(-19.013660431,1.769615293,131.375946045)`;
target dopo `(-18.718608856,1.850307465,131.375976562)`.
Projected displacement `(-0.110240936,+0.403095365,-0.000198364)`.
Il playerStep termina a ghost Y `1.815307498`: il passo verticale originale
di 0.035 spiega l'offset dal target interno, non un clamp diagnostico.
Questo sostituisce la sola ricostruzione offline SLOPE-02 con una chiamata
recovery direttamente osservata.

### Positive requested Y: gameplay precedes Bullet

**CONFIRMED runtime:** il setter riceve target Y uguale a current Y.
Nel primo recovery citato, current gameplay Y `0.011796951`, integrated
9DF0 Y `0.011796951`, ma target 9E20 e request 9E10 Y **`0.684442341`**.
`A047=0`: l'integrazione ordinaria non ha generato quella Y aggiuntiva.
La Y positiva è già presente prima di update/preStep del KCC; non nasce
dentro il recovery. Il ghost ha l'offset di capsula circa 1.4 rispetto a
current gameplay: confrontare quote nello stesso sistema di coordinate.

**CONFIRMED static:** `1E9980` conserva il target in ingresso a 9E20 e il
parametro a 9F24. Il caller normale costruisce target da direzione e current.
`1F69B0` azzera la componente Y della direzione quando `A047&4==0` e integra
in 9DF0. Esiste anche una correzione successiva a `1F70A2`, condizionata da
altri flag, ma nei record citati integrated Y resta current Y.
`1F5240/1F5250` copia 9DF0 in 9E10; il virtuale `+178` entra in **`1F5B30`**.
Questo prepara la query superficie usando la posizione richiesta, con risultato
quota in stack `+50` e normale in stack locale. Con A04C/A01E appropriati
`1F5E15` assegna la quota al target 9E20; per il request esistono il ramo
`1F5E99` e il percorso ordinario A025=0 `1F64DD..1F663D`. Quest'ultimo chiama
`164840` con riferimento a 9E10 e indice componente 1 per assegnarne Y.
Le condizioni alternative di gameplay possono correggere ulteriormente la quota.

**HIGH CONFIDENCE:** questa preparazione superficie fra integrazione e wrapper
è il primo produttore della Y aggiuntiva osservata. La sequenza setter-flat,
integrated-flat, target/request rialzati e le scritture statiche concordano.
Il singolo store effettivo interno a `1F5B30` e ogni risultato intermedio della
query non sono stati instrumentati direttamente: non dichiarare un exact-store
trace né attribuire automaticamente tutto a `1F663D`.
Il boost cambia XZ integrati e quindi il punto interrogato prima del KCC;
preservare solo il parametro originale non conserva questa storia geometrica.
Non applicata divisione della Y di recovery; nessun risultato integrato originale
è stato inventato tramite `requested/multiplier`.

### Preventive cached candidate and controlled results

`--cached-suppress` valuta il cached contact **prima** della moltiplicazione
nel producer: C0!=0, outward normal non-walkable, dot fra target corrente in
ingresso meno current e cached normal positivo. Imposta il latch condiviso
per movement/animation. Il forward wrapper, quando non c'è nuovo hit
qualificante, consulta anche cached C0/D0 e requested reale prima di rilasciare.
Il recovery originale resta invariato. Il log conserva latch prima/dopo e
geometria del producer; il decoder espone transizioni e motivo del gate.
Il flag C0 non viene trattato come ground flag né alterato.

Tutte le catture usano pad software, impulso `x=-0.5, y=0.8660254`, buttons=0,
4.0 s, camera non manovrata, stesso processo/area Anticamera, profilo target
30 FPS preavvio. Nessun nuovo confronto FPS. Direzione world quasi -X con
piccola componente -Z in questa sessione. Yaw/camera numerici non catturati;
il vettore world è letto. Reset con pad e attesa, senza teleport/scritture ghost.
Gli start sono vicini ma **non bit-identical**; non presentare la baseline
come prova causale perfetta dello stesso stato interno al contatto.

| Capture | Move/animation | Ghost start XYZ | Max ghost Y | Cached recovery | Esito |
| --- | --- | --- | ---: | ---: | --- |
| cached-trace-125-01 | 1.25/1.25, vecchio gate | (-6.993392,1.400000,132.793457) | 1.652868 | 0 | esclusa: geometria/lane diversa |
| cached-trace-125-02 | 1.25/1.25, vecchio gate | (-8.114193,1.400000,131.382248) | 8.210943 | 10 | riproduce recovery e ascesa |
| cached-suppress-125-01 | 1.25/1.25, nuovo candidato | (-8.099896,1.400000,131.402527) | 14.217790 | 5 | FAIL; STOP |
| cached-vanilla-01 | 1.00/1.00, solo trace | (-8.462970,1.400000,131.444199) | 1.599308 | 0 | controllo vicino stabile |

**CONFIRMED runtime, candidato:** producer seq15 ha parametro originale
`0.169377014`, target/current Y `0.011368990`, C0=1 e normale
`(-0.964572906,-0.263816476,-0.000101893)`; latch false->true **prima** del boost.
Recovery physical seq299 legge proprio il parametro vanilla `0.169377014`,
latch true e latest producer seq15. Integrated Y resta `0.011368990`,
ma target/request Y diventa `0.076233149`; requested KCC Y `+0.044765744`.
La proiezione originale produce Y `+0.160773635`, ghost after Y `1.572506547`.

| Physical sequence | Latest producer | Parametro durante recovery | Latch | Ghost Y dopo |
| ---: | ---: | ---: | --- | ---: |
| 299 | 15 | 0.169377014 | true | 1.572506547 |
| 301 | 16 | 0.169377014 | true | 1.684026837 |
| 303 | 17 | 0.169377014 | true | 1.894337177 |
| 309 | 20 | 0.169377014 | true | 2.074179411 |
| 311 | 21 | 0.169377014 | true | 2.291207075 |

Nei primi tre producer consecutivi soppressi la quota continua a crescere.
Il terzo recovery aggiunge circa 0.2103 Y: il detector `abs(deltaY)>0.2`
individua già una salita mentre il parametro è vanilla. Quindi la sola
suppression prima della produzione non elimina il comportamento su uno
stato raggiunto precedentemente con boost.
Producer seq18 vede C0=0 e latch true->false: physical seq305 legge parametro
boosted `0.211721271` e ghost supera Y=2. Successivamente il gate torna attivo
nei producer 19/20/21; poi diversi C0=0 lo rilasciano nuovamente mentre i nuovi
hit lo riattivano. **Nessuna stabilità on/off dimostrata.** Il picco 14.217790
include dunque produzione nuovamente boosted: non attribuirlo tutto al recovery
con parametro vanilla. Il problema della suppression e quello del rilascio
sono entrambi osservati nello stesso candidato fallito.

Tutti i quattro log completati riportano restored, conflicts/overflow/invalid=0;
nessuna special call 246. Clip/rate sono quelli del contesto run verificato;
rate getter campionato mostra original 1 e return 1/1.25, ma il suo polling
worker non è una lettura atomica del singolo recovery. Nessuna nuova calibrazione.
Il controllo vanilla termina vicino X=-18.346, mentre l'arrivo boosted aveva
raggiunto circa X=-18.61 al primo cached contact: la storia di posizione/contact
è già differente prima di rendere il parametro vanilla.

**PROBABLE:** arrivo più profondo, query superficie e storia dei contatti
costituiscono il feedback che la sola suppression del parametro non annulla.
Non dimostrato quale di questi stati richieda una diversa architettura;
non chiamare il fenomeno tunneling né correggere la normale/proiezione.

### Stop, cleanup and verification

Stop dopo una failure del candidato, come richiesto. Nessuna seconda variante,
nuovi test flat/ramp/parallel/away, town/combat/lifecycle o implementazione
Sprint. Il solo controllo vanilla vicino completa il confronto diagnostico.
Questi sanity restano subordinati al blocker; nessun READY, default multiplier
approvato o specifica production. Non iniziato Audio.

**CONFIRMED cleanup:** vptr originali player/KCC/channel
`14080AE08 / 140879BD0 / 140822AE8` verificati prima dell'uscita. Gioco chiuso,
pagine private eliminate con il processo; pad neutral/disconnect via finally,
limiter restored `fps:null`. Due mod locali ripristinate nello stato attivo
originale; SKIFsvc32/64 nuovamente attivi. Nessun EXE/CPK modificato, nessun
driver installato, catture e pagine private non commesse.

SLOPE-01/02 è stato salvato separatamente nel commit firmato **`6db581b`**
prima delle modifiche SLOPE-03. La firma 1Password funziona. SLOPE-03 mantiene
separati strumenti e risultati nuovi; nessuna perdita dello staging precedente.
Self-check di `pre_projection`, `slope_trace`, `run_perturb`, `walk_trace`,
py_compile dei quattro tool, parse dei due TOML research e `git diff --check`
passati. SHA-256 EXE invariata rispetto alla build in apertura del report.

### COLLISION-SLOPE-04 — 2026-10-10

**Decisione: NOT READY.** Il singolo blocker successivo è verificare
**equivalenza e stabilità del primo contatto vanilla dopo gli extra separati**.
Il candidato A+C non è approvato: nella seconda prova la quota massima supera
entrambi i controlli. Questo respinge il gate di validazione, ma non dimostra
che il picco sia causato dallo Sprint: start e intervalli nativi non sono identici.
Nessun nuovo latch, patch della collision response, Sprint production o Audio.

#### Trace e store esatti

`tools/terrain_trace.py` usa copie private dei metodi della sola istanza player,
chiamate originali preservate, ring bounded da 8192 record da 512 byte e ripristino
dei vptr tramite `walk_trace`. Registra producer/sequence/thread, parametro
originale/effettivo, current, integration, requested/target prima e dopo,
segmento query effettivo, hit Y/normal/index e submission/ghost del passo fisico.
Le sequenze ordinano gli eventi; non rappresentano frame atomici cross-thread.

**CONFIRMED static + runtime:**

- `+168 -> 20B2A0 -> 1EAE70 -> 1F69B0` produce `+9DF0`.
- `+170 -> 259430 -> 1F5240`: `1F5250` copia integration in `+9E10`,
  poi chiama virtual `+178 -> 1F5B30` e `+180 -> 1EA4E0`.
- `1F5CC0` chiama la query primaria `31EE00`; `1F5D2D` è il fallback
  condizionato al fallimento. `31EED9 -> 6CB920` interroga il segmento verticale:
  start Y = input Y + altezza (osservata 1.2), end Y = input Y - 1000.
  Engine index negativo significa fallimento; `31EF61` ne deriva il bool.
- **`1F5E15`** scrive il target `+9E20` usando la quota restituita dalla query.
- Nel ramo ordinario osservato, **`1F663D -> 164840`**, componente 1 del
  descriptor `+9E10`, passa la quota in XMM1; **`16488F`** scrive requested.Y.

Il trace vede direttamente il caller comune `31EEDE` e l'engine index,
non distingue ogni evento primario/fallback né registra separatamente il bool
finale di `31EE00`. Il punto XZ della query può differire da `+9E10`
(errore massimo osservato nel controllo circa 0.4508): usare il segmento
registrato, non ricostruirlo assumendo uguaglianza. Current gameplay è alla
quota dei piedi; ghost center è circa 1.4 unità sopra, non la stessa Y.

**CONFIRMED writer, cattura `terrain-legacy-125-02`, producer 6:**

| Evento | Valore osservato |
|---|---|
| Parametro originale / effettivo | 0.169377014 (`3E2D712B`) / 0.211721271 |
| Current e integration Y | 0.281662345; integration non aumenta Y |
| Query start | (-19.023054, 1.48166239, 131.646225) |
| Query end | (-19.023054, -999.718323, 131.646225) |
| Hit Y / engine index | 0.356889367 / 1 |
| Surface normal | (0.964573264, 0.263815254, 0.000096804) |
| seq1120, `1F5E15` | target.Y 0.281662345 -> 0.356889367 |
| seq1121, `1F663D` | requested.Y 0.281662345 -> 0.356889367; arg identico alla hit Y |
| Branch flags | A025=0, A04C=1, A01E=1, A021=0, A047=0 |
| seq1122, KCC requested | (-0.574808061, +0.051066637, +0.003540039, 0) |
| seq1123, ghost Y | 1.681662440 -> 1.875444174 |

La Y positiva entra nel KCC già prodotta dal gameplay/query. La cattura arriva
poi a Y=14.21778965. **Non è un nuovo A/B causale:** parte da contatto già
stabilizzato, ghost (-18.328770, 1.40742218, 131.623627), anziché dallo start
della lane. Serve solo a chiudere l'origine esatta della Y. La precedente
`terrain-legacy-125-01` è esclusa: nessun input/setter nella finestra, impulso
arrivato dopo il trace. Nessuna nuova conclusione movement-vs-animation.

#### Valutazione delle architetture

| Candidato | Esito e limite |
|---|---|
| A: extra physical substep | Fattibile come diagnostica bounded: primo wrapper originale, poi secondo passo solo fisico; sync del current osservato. Side effect fisici duplicati e lifecycle non validati. |
| B: extra dopo query, prima wrapper | Preserva il punto query ma non il primo contatto: un unico displacement più lungo conserva il rischio di proiezione già noto. Non adottato. |
| C: capsule preflight dell'extra | Provato insieme ad A usando sweep nativo e shape KCC, non un raycast puntiforme. Il preflight non sostituisce una nuova query terreno per la pendenza. |
| D: spatial substepping | A realizza vanilla + restante 0.25 a livello fisico, senza duplicare il gameplay completo. Non dimostra ancora equivalenza della storia di contatto o handling delle rampe. |

Non tutte le varianti sono impraticabili; A+C ha risultati parziali misurabili.
Non è quindi stata aperta una ricerca aggiuntiva sui metadata Phyre.

#### Preservazione e candidato A+C

Prima dell'extra è stata eseguita `terrain-preserve-01`, con Sprint richiesto
ma parametro effettivo sempre originale: walk 0.04343000054, run 0.169377014.
Nessuna moltiplicazione prima di integration/query. **CONFIRMED** uguaglianza
del parametro nel medesimo producer; **HIGH CONFIDENCE static** conservazione
del primo query path a parità di stato. Le due esecuzioni da start diversi
non sono un replay bit-identico: non esiste una misura runtime accoppiata
`query_Sprint - query_vanilla = 0` dallo stesso identico stato.

Il candidato `--extra` conserva questa produzione vanilla e procede così:

1. Salva il requested KCC `+50`, esegue il primo **`58D340` originale**.
2. Richiede walk-direction `+E3=1` all'ingresso, player verificato,
   F8A6=1/F8AD=0, selector FF/FE e parametro originale `3E2D712B`.
   Per questa diagnostica, `abs(requested.Y) <= 0.001` e primo displacement
   X/Z compatibile con requested entro 0.0002 per componente.
3. Costruisce un nuovo extra XZ = 0.25 del contributo vanilla, Y/W=0.
   Non divide la Y originale e non modifica target, quota query o ghost.
4. Da ghost dopo il primo passo, **`6F8890`** esegue capsule sweep con
   shape KCC `+18`, callback nativa `8C55C0/729CB0`, self e mask/group nativi.
   Margin temporaneo come forward sweep nativo, ripristinato subito dopo.
5. Solo senza hit object invia l'extra tramite **`72A5F0`** ed esegue
   un secondo **`58D340` originale con dt=0**. Il wrapper azzera E3/E4;
   niente extra residuo in idle. Il KCC continua a risolvere entrambi i passi.

Il secondo passo esegue ancora preStep/stepUp/stepDown e sincronizzazione
fisica; non richiama l'intero player update né esplicitamente richieste
animazione, timer e script. **UNKNOWN** assenza di ogni side effect duplicato.
Gli extra accettati dimostrano il ramo no-hit; hit fraction/normal e motivi
di rifiuto del preflight non sono registrati direttamente. Nessuna nuova
strumentazione recovery o contatore completo delle special action: le
esclusioni originali restano, ma questi metrici non sono una validazione nuova.

Animation usa il getter già verificato della sola channel player/clip 122:
1.25 solo con extra accettato, altrimenti vanilla. Un flag DWORD dello stesso
update è inizialmente vanilla, reset dal primo passo attivo e abilitato dal
no-hit; non è un latch cached contact. `terrain-extra-02` osserva rate
1 -> 1 e 1 -> 1.25; il rate nativo 2 resta 2. Poll non atomico, possibili
sfasamenti worker/lifecycle non validati per produzione. Il primo extra trace
non raccoglieva questi poll: corretto `walk_trace` per poll indipendente dal
logger submission, sostituito in questa diagnostica.

#### Prove Anticamera

Pad virtuale, lane storica verificata visivamente, camera non manovrata.
Input (-0.5, 0.8660254), buttons=0, 4.0 s; away usa l'inverso.
Reset bounded tramite pad: start non identici, nessuna scrittura posizione.
Target NVIDIA 30 impostato prima del riavvio; FPS effettivi non misurati
esternamente in questa sessione. Nessuna nuova conclusione FPS.

| Cattura | Ghost start XYZ | Ghost finale XYZ | Max ghost Y | Extra accettati |
|---|---|---|---:|---:|
| terrain-vanilla-01 | (-7.760714, 1.400000, 131.441330) | (-18.304810, 1.407419, 131.623611) | 1.596209049 | 0 |
| terrain-preserve-01 | (-8.475770, 1.400000, 131.635651) | (-18.322227, 1.407422, 131.623596) | 1.595162511 | 0 |
| terrain-extra-01 | (-8.552626, 1.400000, 131.630219) | (-18.246811, 1.407437, 131.623596) | 1.595115423 | 7 |
| terrain-extra-02 | (-8.418660, 1.400000, 131.637726) | (-18.427444, 1.407436, 131.623642) | **1.704176545** | 8 |
| terrain-extra-away-flat-01 | (-18.427444, 1.407436, 131.623642) | (12.037760, 1.474658, 131.000793) | 1.474796653 | 20 |
| terrain-vanilla-02 | (-7.967122, 1.400000, 131.644440) | (-18.473705, 1.407421, 131.623611) | 1.594958544 | 0 |

**CONFIRMED flat extra:** extra XZ / primo displacement vanilla =
0.2499992977..0.2500003559; extra dY=0. Current gameplay X successivo coincide
con ghost X finale precedente (errore massimo 0 nella cattura away).
Away riprende extra senza sticky suppression, inclusi producer 19..28.
Quando requested.Y supera il filtro flat, resta vanilla: non è un test
superato dello Sprint su slope, né una misura di velocità media 1.25 sulla lane.

**Seconda prova, picco producer 57, seq1854/1855:** primo passo originale,
**nessun extra** in quel producer. Ghost prima
(-18.2563763, 1.592821121, 131.623611), dopo
(-18.2868328, 1.704176545, 131.623642). Parametro vanilla 0.169377014;
integration X -18.256376 -> -20.8814468, Y 0.192821025 invariata.
Query hit Y=0.00722324848, normal=(0, 0.999913, 0.013187).
KCC requested=(-0.590133786, -0.041723691, 0.003631592, 0).
Tutti gli otto extra della prova hanno dY=0, max extra Y=1.404827.

Il picco avviene quindi nel primo step nativo dopo gli extra precedenti,
non nel loro substep. La contribution integrata X di circa 2.625 è maggiore
del valore usuale circa 0.677: intervallo/stato nativo non equivalente.
Il controllo successivo resta sotto 1.595; la differenza massima circa 0.108
non chiude il gate, ma non consente attribuzione causale certa allo Sprint.
**Non dichiarare eliminata la collision regression.** Nessun ulteriore
candidato o sanity subordinato dopo questo esito.

#### Gate, limiti e cleanup

Origine query-fed della Y: **CLOSED**. Extra separato e sync sul piano:
**CONFIRMED nel contesto diagnostico**. Primo contatto dopo storia accelerata:
**UNKNOWN, unico blocker successivo**. `COLLISION-SLOPE CLOSED` non raggiunto;
**NOT READY FOR SPRINT IMPLEMENTATION**. Serve un confronto con stato e
intervalli comparabili per distinguere il contatto vanilla dal cambiamento
di storia introdotto dagli extra; non un altro latch o correzione della Y.

Normal slope, stairs, oblique/parallel wall, start/stop, town/combat e lifecycle
restano rinviati. Nessuna specifica production, default Sprint o config READY.
Le catture `.cache/terrain-*.jsonl` sono locali/gitignored; il commit contiene
solo sorgenti diagnostici e documentazione, nessun byte proprietario.

**CONFIRMED cleanup:** vptr originali player/KCC/channel
`14080AE08 / 140879BD0 / 140822AE8` verificati prima dell'uscita; gioco chiuso,
pad neutral/reset/disconnect, limiter restored `fps:null`, due mod locali
attive come prima, SKIFsvc32/64 riattivati. Pagine private eliminate con il
processo; nessuna patch EXE/CPK o installazione driver.

Self-check di `terrain_trace` e `walk_trace`, py_compile dei due tool,
parse dei due TOML research e `git diff --check` passati. SHA-256 EXE
invariata: `1923f0d8d2cad559d6ad6e001af54ea5ea5aa70171323f42d4e1fa3d63699e43`.
Il nuovo trace non raccoglie direttamente ogni native walkable predicate o
recovery event: nessuna conclusione aggiuntiva su quei rami oltre SLOPE-03.
