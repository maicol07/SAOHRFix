# SAOHRFix — Movement report

**Aggiornamento:** le sezioni fino a “Baseline readiness” conservano il report
manuale del commit `ddca350`. Le conclusioni correnti, che sostituiscono le sue
incertezze e lo stato finale storico, iniziano da “Analog input path”.

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
