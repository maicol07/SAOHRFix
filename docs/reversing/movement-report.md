# SAOHRFix — Movement report

**Aggiornamento:** le sezioni fino a “Baseline readiness” conservano il report
manuale del commit `ddca350`. Le conclusioni correnti, che sostituiscono le sue
incertezze e lo stato finale storico, iniziano da “Analog input path”.
La decisione finale corrente è in **“Current validation — 2026-10-01”**:
**NOT READY**, dopo prove live del moltiplicatore e confronto FPS.

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
