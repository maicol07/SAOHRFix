# SAOHRFix — Movement report

**Project discontinued.** The author finished the game and chose to stop spending
time on this project. This English archival edition preserves the findings,
failed candidates, measurements and limitations for anyone who wants to continue.
Repeated checkpoint narration has been consolidated; the original research
snapshots remain in Git history. No new game tests were performed for this edition.

The authoritative **research** decision is COLLISION-SLOPE-07B:
**COLLISION-SLOPE: CLOSED pragmatically — READY FOR SPRINT IMPLEMENTATION**.
That decision permitted an initial implementation; it did not certify production
safety. **Historical integration outlier: UNKNOWN, not reproduced.**

The later native implementation has a separate result: **SPRINT-01B BLOCKED**,
with **zero accepted native Sprint extras and zero animation corrections**.
See [the native implementation record](../sprint-01.md). Research success must
not be presented as a playable native release.

Steam PC build SHA-256:
`1923f0d8d2cad559d6ad6e001af54ea5ea5aa70171323f42d4e1fa3d63699e43`.
Code addresses below are RVAs, image base `0x140000000`; heap addresses and process
IDs are historical, session-specific observations. Sources:
[player.md](player.md), [input.md](input.md),
[addresses.toml](../../research/addresses.toml),
[signatures.toml](../../research/signatures.toml).

Evidence labels: **CONFIRMED** means verified instructions or direct runtime
observations; **HIGH CONFIDENCE** means corroborated attribution without a complete
trace; **PROBABLE** means a hypothesis requiring verification; **UNKNOWN** means
unproven. Static findings and runtime observations are distinguished below.
Initial visual gait descriptions came from the user. Later request/rate reads
are distinct from visual judgments. Sequential polling is not an atomic frame.

## MOVEMENT-01 findings

**CONFIRMED runtime:** the CChrPc → physics ID → Phyre wrapper → Bullet KCC
relationship was identified and rechecked after restarts. KCC displacement changes
with player movement and returns to zero on release. The first physical capture,
identified by the user as keyboard input, had 228 moving samples out of 5,745.
Wrapper scale was 60 while moving and 0 at rest; start/end positions differed and
the backlink remained unchanged. **CONFIRMED static:** wrapper `58CF40` calls
virtual `setWalkDirection` at `58D31C`.

The initial reads used OpenProcess(0x410)/ReadProcessMemory, without debugger,
breakpoints or process writes. Local mods were reversibly disabled, Special K
services stopped and the game launched through Steam. At this checkpoint the
actual caller stack/registers/thread were not captured: attribution of the
observed locomotion chain was **HIGH CONFIDENCE**.

## MOVEMENT-02 findings

Four separate captures lasted about 60 seconds each, with requested 10 ms polling.
Stick percentages were manually estimated; the physical axis was not captured.
The scene was a field, Kirito level 18, three partners; no town/combat tests.

| Requested stick | User-observed gait | Moving samples | Median KCC XZ magnitude | Median CChrPc+9F24 |
|---|---|---|---|---|
| Approximately 25% | Walk | 294 / 5,742 | 0.021488 | 0.043000 |
| Approximately 50% | Uncertain | 929 / 5,740 | 0.021976 | 0.043000 |
| Approximately 75% | Run | 618 / 5,746 | 0.024467 | 0.043000 |
| 100% | Run | 345 / 5,728 | 0.080614 | 0.167700 |

**CONFIRMED:** the full-stick median parameter is approximately 3.9 times the
other captures; the median walk-vector/KCC+100 ratio is approximately 1/60.
Distinct gait/speed selection was **PROBABLE**, but these data alone did not
reconstruct an analog curve or threshold. The visual 75% run description and
0.043 median were inconsistent. KCC magnitudes are displacements, not u/s.
Variable dt, terrain, non-atomic reads and movement windows differing from the
requested three seconds prevent deriving speed by dividing total travel by 3.

Earlier nonfunctional-pad attempts were excluded. Input worked after another
Steam Play launch; the reason was **UNKNOWN**, not proven hot-plugging behavior.

## Player controller

**CONFIRMED:** CChrPc vtable `80AE08`; modified controller
PModifiedBulletKinematicCharacterController vtable `879BD0`, derived from Bullet
btKinematicCharacterController vtable `8C5550`.

```text
CChrPc+9FCC -> physics ID
[image+B148B8] -> global object -> manager
manager+18 -> record pointer array; manager+134 -> count
record first dword == physics ID
record+10 -> wrapper
[wrapper+148] -> KCC
[KCC+F0] == wrapper
```

Lookup `6CBEB0` returns the array slot, which must be dereferenced. Controller
creation begins at CChrPc virtual +140 (`1EF070`), not +28. Example session
PID62148: player21458890, physics10, wrapper20D81D60, KCC80DF3CF0. These are not
constants to reuse after loading or restarting.

## CChrPc locomotion chain

The initial static reconstruction was **CONFIRMED** for instructions/offsets and
**HIGH CONFIDENCE** for its use during the manual captures:

```text
205BC0 -> 208FD0 -> derived locomotion parameter
  virtual +3E8 -> 1E9980: target +9E20, parameter +9F24
1EAE70 -> 1F69B0: normalized target-current -> integration +9DF0
1F5240: integration -> requested position +9E10
  virtual +178 -> 1F5B30: surface preparation (traced in SLOPE-03/04)
  virtual +180 -> 1EA4E0 -> 320310
    requested-current -> wrapper+40; scale -> wrapper+F4
6CC090 -> 58CF40
  transformed displacement * wrapper scale -> KCC+100
  KCC+100 * update scalar -> setWalkDirection argument
58D31C -> virtual +18 -> 72A5F0 -> KCC+50
```

There are other requested-position writers. Initially this was not a recorded
runtime stack; `58D31F` was the statically expected return address. Later
diagnostics confirmed the callers and localized the intervening terrain writes.

## Movement speed source

**CONFIRMED static:** `274220` returns table `AEAB70`; initialization `1FE6D0`,
store `1FEA03`, copies table+28 into player+9F20. Getter `208FD0` starts there,
applies state/stat modifiers, calls `1BAF30` and clamps. `205BC0` stores +9F24.

| Item | Value / location | Initial evidence |
|---|---|---|
| Base parameter | Player+9F20 | Static CONFIRMED |
| Derived parameter | Player+9F24 | Static/runtime CONFIRMED |
| Base table | AEAB70+28 = 0.043 | Runtime CONFIRMED |
| Factors | Table+30=3.9, +34=3.9, +38=1.38 | Runtime CONFIRMED |
| Branch selectors | Virtual+648, F8A6, F8AD | Instructions confirmed; meaning initially UNKNOWN |

The initial 0.043 × 3.9 explanation was **HIGH CONFIDENCE**, without a moving
flag witness. +9F24 is a derived parameter, not a proven universal maximum speed.

Writer `69B430`, called at `696143`, produces a clamped app_dt×60 scalar in
A63240; `69B4C0` supplies it to integration, further scaled by player+9FE8.
An early sample was app input 0.0096343, reciprocal103.7958, step0.578058.
Seconds/frame-at-60-Hz interpretation was **HIGH CONFIDENCE**. Applying dt in
seconds again would be incorrect. Initial wrapper timing uncertainty was resolved
in later sections; the early 1/60 ratio alone did not resolve it.

## Animation relationship

At the manual baseline, gait selection, root motion and playback coupling were
**UNKNOWN**. Phyre metadata names PCharacterMotionGait, m_speedMultiplier,
m_motionAnimSpeedScale and m_animSpeedLimit did not establish that CChrPc used
them. Visual gait reports did not prove that faster movement would synchronize
footsteps. Later diagnostics established **Case B: movement speed can increase
while run playback remains 1.0**.

## Recommended Sprint hook

The initial candidate was getter `208FD0`, or its player-specific consumption
in `205BC0` before +9F24. It was a plausible upstream PoC point, not an approved
safe hook. Existing walk/run mode, Bullet argument and requested-position delta
were alternatives with unresolved timing/animation/combat behavior.

**Superseded:** later collision work rejected a simple upstream multiplier as
the implementation architecture. The final research candidate is vanilla-first
A+C: preserve gameplay/query/first physical step, then add a capsule-preflighted
XZ-only physical substep. Do not revive the upstream recommendation as current.
No global table, NPC, final position or collision response should be patched.

## Baseline remaining unknowns

The manual baseline lacked the actual Bullet caller/register/thread capture,
consumed analog axes/threshold, selector meaning, wrapper/FPS validation,
animation response, town/combat coverage and collision-multiplier tests.
These were historical gaps, not all current blockers; later sections supersede
them individually.

## Baseline readiness

**Historical decision: NOT READY.** Player controller and speed production were
identified; caller runtime, stick threshold, dt and animation/collision behavior
were incomplete. The reader self-check, Python syntax, TOML and four new unique
build-local signatures passed. Changes were uncommitted and the initial mod/SK
state had not yet been restored at that checkpoint. Later cleanup records
supersede that temporary state. No Audio/INPUT-01/STATE-01/Sprint implementation
had begun.

## Analog input path

**CONFIRMED static/runtime continuation:** `205BC0` obtains axes through
AEA4A0/1CE560. Calls `205C31 -> 2D0290` and `205C4B -> 2D04D0` request X/Y
with history EDX=0. Signed 16-bit axes reach R12D/R15D. Ring C66D60 has stride8C,
axes+80/+82, countC69060, cursorC69068; history64 uses
`(cursor - 1 - edx) % 64`. Axis-object+70E inversion was not captured live.

The diagnostic `1E9980` setter returns to `1E993F`; outer caller `206660`
retains X² in R12D and X²+Y² in R15D. Observed sums include 10201,10404,16129,
16384. Squared values lose signs and this register interpretation is caller-specific.

Virtual Xbox input used the existing ViGEmBus and project-local vgamepad0.1.3;
no driver was installed. The sweep used 0/10/20/30/40/50/60/65/70/75/80/85/90/
95/100%, two seconds active plus one neutral. Requested percentages are not
universal internal values. An approximately115-second probe rejected114 cursor
changes; maximum read span was1.376ms. Cross-thread records retain the latest
producer, not a proven atomic gameplay frame.

## Walk/run threshold or curve

**CONFIRMED static:** `20646A` compares sum-of-squares with 0x3100=12544=112².
Below threshold it resets F8A6/F838. Above threshold, if `20AD30` permits it,
the `1E6090 -> 69B4C0` timer accumulates until >10, approximately10/60 seconds.
Related getters `1E6DA0/1E6D70` were not given speculative gameplay names.
Keyboard can select run through this path.

| Consumed axis bins | Result |
|---|---|
| +69,+85,+93,+101,+109 | Walk |
| -70,-86,-94,-102,-110 | Walk |
| +117,+125,+127; -118,-126,-128 | Initially walk, then run |

Below-threshold bins had190–192 samples each. +117 and -118 each had16 walk
and175 run samples. Bins111/112/113 were not individually isolated live.
The parameter changes 0.043→0.1677, rather than scaling continuously with stick
magnitude over these bins. This supersedes the manually estimated75% ambiguity.

## Selector semantics

Virtual+648=`20AB60` negates the embedded A9E0 object (vptr80A8F0), slot40
`20A740` -> slot60 `20A750`. Verified context has A9E9=FF and A9F0=FE. It is
true at idle, walk, run and reversal; it is not an IsRunning predicate.
F8AD remained0. In the true branch F8A6 selects run factor table+30=3.9;
F8AD uses table+18=1. The false branch uses +9F88 and table+34=3.9/+38=1.38.
Same-producer observations linked F8A6=0 to0.043 and1 to0.1677, with base unchanged.

At +127/sum16129: first walk14.842476s, first run15.007770s, delay165.294ms.
At -128/sum16384:18.840674→19.007919s, delay167.245ms. These are polling
observations compatible with the static timer, not exact timer-resolution proofs.

## Runtime call confirmation

Player slots+3E8/+460 and KCC+18 used instance-only private-vtable logging
shims, preserving original calls, arguments, flags and registers. Runtime confirmed
`205BC0 -> 1E98A0 -> 1E9980`, return1E993F/206660, rotating worker threads.
Bullet return58D31F, wrapper return6CC141, manager return6CBDA5 were observed.
A final60-second capture had8,889 submissions,5,729 observed. PID52256,
player213A7890,physics10,wrapper20CD0D60,KCC80DF9CF0,thread76948 were session-only.
Private allocations grew from4KB to8KB and were retained until process exit
after restoring original vptrs; this was bounded instrumentation, not a production
lifecycle manager.

## Framerate behavior

The app scalar is clamped to[0,60]; player+9FE8 was1. The wrapper's factor60
and update scalar1/60 cancel once. Example pre-vector
(0.039585114,0.009484291,-0.068557739) became
(0.039585110,0.009484290,-0.068557732). Constant1/60 is at81FD40, correcting
the earlier820D40 attribution. XMM6 is the scalar; XMM9 is overwritten by a vector.
RequestedXZ/dt medians approximately2.58 walk and10.062 run were not yet actual
world-speed measurements. Early6–8ms poll dt did not establish rendering FPS.
Later externally observed30/120FPS corridor measurements are recorded below.

## Animation/gait relationship

Player virtual+460=`1DDC10` writes rate+90F0 and short request+90F8. Consumer
`1F6730` resets owner+4C0; `287E90` writes channel+1E8. Runtime observations:

| State | Request | Rate | F8A6 |
|---|---:|---:|---:|
| Idle | 0 | 1 | 0 |
| Walk | 100 | 2 | 0 |
| Run | 122 | 1 | 1 |
| Other action | 246 | 1 | 1 |

Callers2B7FDE/2B7EFF and other-action2C44E1/2C4AD0 were observed. A request
number was not initially a named final clip. Getter+4B8=`209370` branches on
`1E6DA0`, +8D8=`207FA0`, `1E6D70`, F8AD, without directly reading F8A6.
The alternate208FD0/metadata1E4C00 branch was not observed. No root-motion
semantics were inferred from metadata names.

## Sprint hook recommendation

At this historical checkpoint, `1E9980` before +9F24 was a player-specific
diagnostic candidate only. No PoC was approved before FPS/animation validation.
The eventual implementation architecture is A+C, described in SLOPE-04 onward.

## Sprint PoC results

Initial instrumentation established input, speed selection and original calls;
it did not itself alter speed. Later upstream1.10/1.25 PoCs proved actual speed
increase and Case B playback, but collision work rejected that architecture.

## Collision tests

Early manual/probe captures were not collision-multiplier validation. The later
wall tests, controlled Rastoria series and SLOPE-01–07B provide the relevant
evidence. Different starts and lanes are stated explicitly below.

## Remaining unknowns

At this checkpoint FPS, playback coupling and multiplied collision behavior
remained open. Town/combat and production lifecycle were untested. These
historical unknowns must be read with the subsequent decisions.

## Phase 1 Sprint readiness

Historical result remained **NOT READY** pending actual FPS, animation and
collision validation. Left Shift/L3 and configurable Hold/Toggle were future
binding requirements, not implemented input features at this stage.

## Final state of the diagnostic continuation

Original vptrs were restored; pad neutralized/disconnected. Some early private
pages remained until game exit. Local mods were temporarily left disabled and
Special K stopped at this checkpoint. DSX/driver state was not changed. Later
session cleanup records establish their own final state rather than inheriting
these temporary settings.

## FPS/animation checkpoint — 2026-10-01

The setter diagnostic filtered the active player and exact baseline bits. It
supported1.10/1.25, but initially neither perturbation had been run. An existing
NVIDIA profile override began with SETTING_NOT_FOUND. Requested cap30 produced
app_dt≈0.06666 (~15 physical submissions/s); changing to60 while running did
not change cadence. Restarting with60 produced≈0.03333 (~30/s). These were cap
and cadence observations, not external FPS measurements. An idle45-second
capture had1,345 submissions and did not validate movement.

Ghost `[KCC+10]` has vptr8C3F08 and origin+40. At idle its XZ matches player;
Y is approximately1.4 above gameplay feet. Preliminary cap30 captures:

| Pad | Moving time | Net XZ | Net speed | Y range | Exclusion |
|---|---:|---:|---:|---:|---|
| (0,+127) | 4.8494s | 1.3442 | 0.2772 | 0.2819 | Obstacle blocked |
| (0,-128) | 4.8576s | 45.6614 | 9.4000 | 2.5279 | Uneven terrain |

Both used0.1677 and requestedKCC/dt≈10.062. Neither was a flat speed control;
an earlier rough9DE0 capture was also excluded. Clamp steps4/2 at caps30/60
were well below saturation60.

Animation chain: `28B720 -> 287E70` selects controller+2F0+8*index;
`287E90` writes channel+1E8. Channel vtable822AE8 slot30=`6C6C80` returns
`[A65970] * [channel+1E8]`; global factor was1, not dt. `2888A0` calls at
2888C9 (return2888CC), moves XMM0→XMM1, calls6C5A00, stores+1D0, then
6C5360/6C550F. `6C5619` loads1D0 intoXMM2; `6C5621 -> 56E530` updates
animation records of strideB0, fields+C/+50/+54. Initially only idle downstream
was observed. No playback correction PoC had been run.

The user interrupted Computer Use with Escape; no further UI input followed.
An invalid pad command lacking buttons was rejected before input. Player/KCC/
channel vptrs80AE08/879BD0/822AE8 were restored. PID83096 was left responsive
with private8KB retained until exit. At this checkpoint limiter `fps:null` was
confirmed restored, local mods remained disabled and Special K was not yet
restored. Self-checks passed; those were not live perturbation tests.

## Current validation — 2026-10-01

### FPS and flat corridor

A clean Steam launch omitted local mods/global Special K; an initial injected
process was discarded. NVIDIA overlay externally showed30 and120–121FPS during
movement, not a Present trace. Cap60 lacked an independent effective-FPS measure.

| Requested cap | External FPS | App dt | App step | Physical cadence |
|---|---|---|---|---|
| 30 | 30 | 0.066664–0.066669 | 3.9998–4.0001 | Approximately15Hz |
| 60 | Unverified | 0.033318–0.033327 | 1.9991–1.9996 | Approximately30Hz |
| 120 | 120–121 | Approximately0.016663 | Approximately0.9998 | Approximately60Hz |

Why physical cadence differs from displayedFPS remained **UNKNOWN**. The corridor
was X≈-6.5/-6.7,Z132–183, Y range≈0.50–0.54 over48XZ units: nearly flat,
not mathematically horizontal. Pad(-0.8660254,-0.5) and its inverse produced
consumed(-111,64)/(110,-64).

| Condition | Time s | Net XZ | Net u/s | Path u/s | Y range |
|---|---:|---:|---:|---:|---:|
| 30 outbound | 4.8003 | 48.2869 | 10.0591 | 10.0591 | 0.5005 |
| 30 return | 4.8035 | 48.2960 | 10.0544 | 10.0544 | 0.5077 |
| 60 outbound, no effective boost | 4.8031 | 48.2939 | 10.0547 | 10.0547 | 0.5310 |
| 60 return | 4.8332 | 48.4731 | 10.0291 | 10.0422 | 0.5354 |
| 120 outbound | 4.8167 | 48.4482 | 10.0584 | 10.0584 | 0.5076 |
| 120 return | 4.8385 | 48.6259 | 10.0498 | 10.0504 | 0.5119 |

Mean30/120 difference≈0.03% supports **HIGH CONFIDENCE** consistency in this
corridor; polling is not precision metrology. Excluded: first cap30 path nearX10
with Y range1.10–1.44/rocks; first cap60 deviated path (net9.8289,path9.9435).
Walk:2.9624s,7.6515XZ,2.5828u/s,parameter0.043,Y range0.5424. Clamp4 at30FPS
corresponds to1/15s; wrapper60×1/60 remains unchanged, with no double-dt.

### Upstream speed PoCs and Case B

The first1.10 attempt incorrectly matched3E2BB98C=float32(0.1677); actual run
was3E2BB98D, one ULP higher. Exact-bit filtering was corrected rather than
widening eligibility. At1.10, parameter0.1844700128, requestedKCC/dt11.0682:
cap60 outbound/return times4.8338/4.8094s, distances53.4749/52.9701,
net11.0627/11.0139u/s, path11.0633/11.0280. Walk/base remained original;
run122 playback remained1.0.

At1.25 parameter0.2096250057, requestedKCC/dt12.5775:

| Condition | Time s | Net XZ | Net u/s | Path u/s |
|---|---:|---:|---:|---:|
| Cap60 outbound | 3.8009 | 47.7894 | 12.5731 | 12.5731 |
| Cap60 return | 3.8052 | 47.5901 | 12.5064 | 12.5283 |
| Verified30FPS outbound | 3.8004 | 47.7939 | 12.5759 | 12.5760 |
| Verified30FPS return | 3.7961 | 47.4335 | 12.4952 | 12.5358 |

Y ranges≈0.52–0.53. **CONFIRMED Case B:** actual movement increases but
downstream run rate stays1.0. Walk downstream2 and run1 were confirmed through
request/getter/channel1E8/1D0. Phase1D4 wraps; rough start/end values (baseline
~8→11.93, boosted~8.18→19.98) were not clip durations. Logging can lose events
and is not atomic. Two9DE0 reads one second apart after stopping showed XZdelta0;
this was not stop-latency measurement.

### Historical wall anomaly

At1.25/cap30, start(-7.635,1.4,131.370) ended
(-21.823,13.401,131.564),3.7905s,Y range12.0007; return range12.8185.
A later vanilla attempt started(1.131,1.4,130.672), ended
(-18.485,1.594,131.301),3.7924s,speed5.175,Y range0.1982.
**Different starts/lanes make this causally insufficient.** No tunneling claim
was established. Town/combat and playback correction were deferred: **NOT READY**.
Cleanup restored vptrs, closed game, reset/disconnected pad, confirmed fps:null,
disabled NVIDIA overlay, restored initial local-mod-disabled state and running
Special K32/64 services.

## Collision reproduction and playback calibration

Anticamera historical input: pad(-0.5,0.8660254),buttons0,4.0s, camera unchanged;
consumed(-65,-111), world approximately-X with small+Z. Requested cap30/appdt
~0.06666 was not a new external FPS measure. Pad resets used no position writes;
nominal ghost(-7.673,1.4,131.388), actual starts differed. PID61044/player213C2890
and reloadedPID77596/player213BD890 were session-only.

Selector changed FF→1 with parameter0.1090050042 and clip100122; guards correctly
suppressed. Excluded100-2/3,110-1/2/3,125-4/5 and first animation baseline, plus
an initial wrong-start approach. New captures required verifiedFF/FE. Effective
parameters were0.1677000076/0.1844700128/0.2096250057.

| Factor | Run | Start X | Start Z | Max ghost Y | Detector events |
|---|---|---:|---:|---:|---:|
| 1 | 1 | -7.6729 | 131.3875 | 1.6011 | 0 |
| 1 | 5 | -7.7246 | 131.4068 | 1.5971 | 0 |
| 1 | 6 | -7.7688 | 131.4069 | 1.5966 | 0 |
| 1 | 7, later | -7.4314 | 131.4036 | 1.6380 | 0 |
| 1.10 | 4 | -7.8038 | 131.4064 | 3.7950 | 9 |
| 1.10 | 5 | -7.4889 | 131.3863 | 1.6138 | 0 |
| 1.10 | 6 | -7.7938 | 131.4064 | 1.7439 | 0 |
| 1.25 | 1 | -7.4718 | 131.4006 | 1.6452 | 0 |
| 1.25 | 2 | -7.6900 | 131.4227 | 1.6422 | 0 |
| 1.25 | 3 | -7.5564 | 131.4245 | 1.6427 | 0 |
| 1.25 | 6, reload | -7.6345 | 131.3846 | 1.6442 | 0 |

All startY=1.4. Baseline100-4 atZ131.4999/Ymax1.595 was excluded as a different
lane. Detector was abs(sampledΔY)>0.5 orabs(Y-start)>2; sampled events are not
individual physical frames. Getter729EC0 slot58 is true when KCC+20/+24 are
float zero, not proof of foot contact. Native step-up72AE80 uses+44=0.035,+48=0.02.

110-4 rose1.4→3.795→1.408 with original parameter0.5,clip246,setter return1F625A,
which the multiplier excluded. Witness ghost(-18.9486,3.0510,131.5546),playerY1.651,
targetY2.0868,requestedY+0.61936; ground gettertrue,+20/+24zero,flags1/0/1/0.
Max sampledΔY1.0643 was not a single-frame delta. Static1F6219 loads constant
904F90=0.5;1F6254 calls virtual+3E8,return1F625A. Upstream special-action origin
was **HIGH CONFIDENCE**; a vault-like interpretation **PROBABLE**, action name
unknown. Four stable1.25 runs and this1.10 event did not establish a monotonic
threshold or justify choosing1.20 as safe. The old13.4 excursion was not fully
reproduced in this series.

### Animation calibration method and pairing

Static286F80→6C5E30 selects active descriptor using index+114,descriptor array+A8,
count+B8,stride40 decimal,ID+18;6C48B0 validates. InFF/FE IDs were0/100/122;
selector1 produced100000/100100/100122. Ephemeral request+90F8 is not the active
descriptor. The getter shim changed only the verified player channel, active
clip122,original return1.0; no globalA65970/channel1E8 writes. Return-address
guard2888CC was added after these captures and self-checked, not separately
live-validated at this checkpoint.

Three-second alternating flat impulses at movement1.25 measured12.53–12.56u/s.
Channel1E8 stayed1; downstream1D0 reflected the selected factor. The first
clip100122 trial was rejected and repeated inFF/FE. Cadence proxy used positive
phase increments and traveled distance, excluding wraps, clip transitions and
gaps>0.15s; no assumption about phase units, no foot-bone world transforms or
high-FPS foot-contact video.

| Move | Animation | Phase/s | Distance/phase | Difference from baseline | Collision / sliding qualification |
|---|---|---:|---:|---:|---|
| 1.00 | 1.00 | 59.715 | 0.167700 | Baseline | Reference |
| 1.10 | 1.00 | — | — | Uncalibrated | One246 event in three effective wall runs |
| 1.20 | — | — | — | Not tested here | No safe pairing established |
| 1.25 | 1.10 | 66.558 | 0.195600 | +16.6% | Direct sliding unmeasured |
| 1.25 | 1.15 | 68.582 | 0.182280 | +8.7% | Direct sliding unmeasured |
| 1.25 | 1.20 | 72.508 | 0.174696 | +4.2% | Direct sliding unmeasured |
| 1.25 | 1.25 | 74.639 | 0.167084 | -0.4% | Best distance/phase proxy |

Baseline had52 usable intervals; factors had38/38/37/37. **HIGH CONFIDENCE:**
1.25/1.25 best matches baseline distance per phase within this method. This does
not measure foot sliding directly or establish a release default. Getter math
does not accumulate a global factor. Identity change aborts; channel returns
original, activation clears, vptr restores and code remains until exit. Respawn
and concurrent destruction were not validated. At this checkpoint TRACE-246
remained the next blocker; cleanup restored instances, closed game, disconnected
pad, confirmed fps:null, restored original mods/Special K and passed self-checks.

## TRACE-246-01 — static preparation, 2026-10-02

Unwind range1F6045–1F6296 belongs to1F5B30. At the special setter RDI=player,
R12D=0,R14=player+9E10,XMM9=0. The parent saves three registers and allocates150;
parent return is entryRSP+170, not the normal206660 caller offset.

**CONFIRMED static conditions:**

1. A021=0, virtual+530(2) true, A047 mask4 absent.
2. A025!=0 at1F5F00.
3. QueryY inXMM11 exceeds requestedWorldY+XMM2 at1F603B;
   1F6001–1F6026 updates9F58.
4. A025!=0 and9F58<0 at1F6060/1F606D.
5. 9FDC*pi/180 exceeds the1ADC40-derived angle at1F61C4.
6. 9FF8<600 at1F61D6.

1ADC40 angle attribution is **HIGH CONFIDENCE**: arguments normalY and
sqrt(nx²+nz²), with complementary-angle conventions distinguished. ZeroXZ uses
XMM11=1 rather than an assumed atan2. `1F60C6` assigns requestedY=query height;
1AD750 normalizes normalXZ; target adds0.5*(1-normalY) along horizontal normal.
The setter parameterXMM2 is separately0.5. This is not KCC step-up.

| Field | Writers / reads / limits |
|---|---|
| A025 | Set1 at1F4237/1F43A7; reset1E1F10/20E4F7; descriptor+14 bit0 copied at22804E/248BD9; read1F5F00/1F5F40/1F6060/getter1E7530 |
| 9FDC | Constructor1DA691 sets50; read1E0D30/1F61AC;23A923=-15 belongs to another class, not a live player observation |
| 9FF8 | Constructor1DA676 sets0; reset1F5EEC/1F62FC/1F6619/1F6642; increment1F6273; read1F61D6/1F626B;600 is not established seconds |

Surface query31EE00 is called at1F5CC0, fallback1F5D2D perturbsXZ by0.001.
The vertical ray goes from requestedY+max(9FC8,1.2) to requestedY-1000 at the
sameXZ, through6CB920. HitY+60/normal+80 are copied into locomotion stack+50/
RBP-80; dual failure selects fallbackA04C=2. This is **HIGH CONFIDENCE** vertical
surface preparation, not a forward vault test.

After setter return1F625A,1F6260 invokes virtual+428=`20D0C0 -> 1F4230 -> 2C4450`
on player+A9B8. If1E59D0 returns0,2C449E sets state4 through+4F0=207AD0→1E4840.
State4 table contains206,246,952,956,960,964; virtual+448 chooses206/246.
2C44DC→1DDD70→player+460 returns2C44E1, then169210 transitions.
Virtual+448=`1E7F30` requires A01E!=0 and+438=20AD60 false. With A03C=0,
+438 reads A01E and returnsF8A6==0, hence A01E=1/run=1 selects246. With
A03C!=0 it uses1E7970/+9F24. Other+428 callers1F65E0/1F6613 mean clip246 alone
does not prove caller1F625A.

The12KB private trace recorded only setter return1F625A with parent caller,
fields,XMM2/XMM11,surfaceY/normal/requestedWorld. Polls associated other fields
sequentially; they did not atomically trace the entire parent instruction stream.
At the initial checkpoint shim exclusions were tested, trigger body was not.

Native SKIF Stop/Start resolved an inaccessible UI; mods.ps1 regex grouping was
corrected so original filenames restored. Initial smoke was in Foresta Grilim,
ghost(-619.990,21.167,-383.600), not the historical lane.30s/450 polls had387idle/
63walk;20s/300 polls had253idle/2walk/45run. A025=0,9FDC=50,9FF8=0,9F58=0,
zero special calls. Pad(0,1),3s,buttons0,factors1; restored. No causal comparison
was drawn from the wrong area. **NOT READY** pending historical-lane access.
Cleanup restored vptrs, closed game, reset pad, confirmed fps:null and restored
local mods/Special K. Self-checks passed.

## Historical area identified and access established

The user identified **Anticamera delle Grandi Pianure Rastoria** on October2.
Historical start≈(-7.67,1.40,131.39),pad(-0.5,0.8660254),4s,world-X/small+Z,
camera unchanged. Initial navigation reached Poggio Phoeniath and returned to
the plaza; a plaza door did not transition. This did not prove other routes
inaccessible, and no capture hooks ran during navigation.

On October7 the unlocked plaza teleporter → Rustoria regional map → castle node
directly reached the UI-labelled Anticamera. Walking through Arktarium was not
needed for this save. Arrival ghost was(36.129,1.849,178.775).

## TRACE-246-01 — Anticamera reproduction, 2026-10-07

Vanilla100-4 started(-7.894,1.4,131.640);125-2/3/4 started
X=-7.912/-7.958/-7.931,Z=131.638/131.635/131.639. Relative errors were bounded
(X≤0.065,Z≤0.006), butZ differed≈0.25 from historical131.39. Other comparable
starts hadX[-8.10,-7.18],Z[131.535,131.640]; firstvanilla started
(-6.465,1.4,131.310). Actual trajectories diverged; no bit-identical replay or
numeric camera/yaw record was claimed.

New vanilla walk0.0434300005/run0.169377014, exact bits3E2D712B, differed≈1%
from the older baseline for an **UNKNOWN** reason. Bounded --baseline-bits
accepts only explicitly measured3E2D712B or historical3E2BB98D, not auto-learning.
Effective boosted parameters:1.10=0.186314717,1.15=0.194783568,
1.20=0.203252420,1.25=0.211721271.

| Condition | Captures | Max ghost Y | Special-call counts |
|---|---|---|---|
| Vanilla | 100-2..6 | 1.5970,1.5938,1.5953,1.5955,1.5964 | All0 |
| 1.10/1.10 | 110-1..3 | 1.6132,11.6899,1.6132 | All0 |
| 1.15/1.15 | 115-1..2 | 1.6240,14.2178 | All0 |
| 1.20/1.20 | 120-1..3 | 1.6343,1.6319,1.6356 | All0 |
| 1.25/1.25 | 125-2..4 | 1.8493,4.7948,3.1188 | 0,0,11 |

Excluded:100-1 ended before motion;125-1 failed the old-baseline guard;115-3
started(-12.260,1.4,131.624) after an event and was not comparable;100-7 had
other selector/clip100000/101152,request1152,caller1F54E4;115-4 had no valid
capture/stderr record. Detector sample counts56/132/25/8 in110-2/115-2/125-3/
125-4 are not CPU-event frequencies. Three stable1.20 captures did not prove a
safe threshold.

### Ordinary ascent versus original special action

110-2/115-2/125-3 rose through ordinary return1E993F,clip122,A025=0,A021=0,
A01E=1,A03C=0,A04C=1,9FDC=50,9FF8=0, with no246 calls. Negative9F58
(-0.432666/-0.154300 in110/115) did not satisfy the A025 gate. Ghost/playerY
rose together with the usual≈1.4 offset. TargetX≈100 ahead did not prove mesh
penetration. Observed dY/-dX slopes3.656299(n41),3.656283(n36),3.656224(n30)
matched normalNx/Ny3.656245. Some negative requestedY samples accompanied
positive actualY (8/41 in110,14/30 in125), compatible with projection but not
an atomic proof at this stage. KCC fields0/0.035/0.02,flags1/0/1/0 and ground
getter0/0 were not interpreted as foot-contact evidence.

125-4 had11 special calls and11 trace records,parent1F5271,setter return1F625A:

| First special record | Value |
|---|---|
| A025/A021/A01E/A03C/A04C | 1/0/1/0/1 |
| 9F58 | -0.031180203 |
| 9FDC / 9FF8 | 50 / 0, later up to16.025543 |
| QueryY | 1.773118377 |
| Surface normal | (0.964573264,0.263815254,0.000096804) |
| AngleXMM11 | 0.266975462rad <50*pi/180 |
| SetterXMM2 | 0.5 in all11 records |
| Requested world | (-19.410387,1.773118,131.547394) |
| Polled target | (-19.042295,1.773118,131.547424) |
| Ghost/playerY | 2.866334/1.466334 |
| KCC requested | (-0.550432,+0.717651,+0.003372) |
| Request / clip / rate | 246/246/1 |

Twenty-one polls observedclip246/rate1; both hooks exclude that path. Polls
occasionally retained an older1.25 rate, which is not a synchronized violation.
**CONFIRMED:** original246 special path. **PROBABLE:** Sprint favors entering
it (1/3 versus0/5 here), not a causal proof. No direct parameter/playback
amplification of that path was observed. Ordinary large ascents were unrelated
to executing246; therefore the whole collision blocker could not be closed as
a harmless vanilla special action. Next blocker was ordinary KCC projection.
All20 completed captures restored; cleanup returned game/mod/SK/pad/limiter
state and static checks passed. **NOT READY**.

## COLLISION-SLOPE-01 — 2026-10-09

### Synchronized KCC trace

`slope_trace.py` records six snapshots in one player-KCC update: before/after
wrapper58D340,preStep72A160,playerStep729EF0. Instance callback+60=`5875A0`
shares sequence/thread. Original calls/arguments remain intact; no ghost,Y,
step-height or collision writes. Records include ghost/current/target,requested+50,
direction+60,state20..4F,C0..CF,D0,E0..EF,contact normal/point and callback
before/after positions. Schema2 adds forward-caller72ADDB fraction and latch.
Ring4096updates×7callbacks publishes after completion; conflicts/overflow
invalidate capture. Player/query/animation polls remain separate. Two KCC
updates per submission with alternatingE3 are not independent video frames.

### Movement/animation separation

Same area, unchanged camera, pad(-0.5,0.8660254),buttons0,4s,requestedcap30
before restart, no new externalFPS check. Poll dt≈0.0667,wrapper scalar≈1/60.
Reset starts are bounded, not identical. DetectorsY>2 orabs(updateΔY)>0.10
are diagnostic; small normal corrections can exceed the latter.

| Move/animation | Capture | StartX (Y1.4,Z≈131.64) | Max ghostY | Result |
|---|---|---|---|---|
| 1/1.25 | slope-30-A1..3 | -7.772,-7.814,-7.831 | 1.5950,1.5952,1.5950 | No large ascent |
| 1.25/1 | slope-30-B1..3 | -7.772,-7.790,-7.830 | 1.6466,1.6410,1.6417 | No large ascent |
| 1.25/1.25 | slope-30-C1..3 | -7.779,-7.803,-7.811 | 1.6412,1.6411,1.6414 | No large ascent |
| 1/1 | slope-30-D1..3 | -7.737,-7.778,-7.826 | 1.5956,1.5947,1.5945 | No large ascent;D1Z131.606 |
| 1.15/1.15 | slope-30-115-near-old | -7.296160,Z131.641861 | 5.3738 | Ordinary ascent reproduced |
| 1.15/1 | slope-30-115-move-only-2 | -7.407774,Z131.637878 | 14.2178 | Ordinary ascent reproduced |

All had zero special calls/conflicts/overflows and reported restoration. Effective
1.15 parameter0.194783568. Stable cap60 A/B/C/D captures did not replace cap30
tests; movement-only-1 had no effective input and was excluded.
**CONFIRMED:** faster playback is unnecessary for ascent. Animation-only was not
proven harmless at every start; stable1.25 trials do not cancel earlier failures.

### Projection and first positive delta

Forward72A9D0 calls72B3C0 at72ACC8 before callback72ADDB. For unit normal and
XMM3=1, the result is `v - dot(v,n)*n`. Implementation normalizes/reflects,
removes normal component and restores length, with no explicit division byNy.
ProjectedY is computed72B597, targetY stored72B5EA; ghost published72A139.

| Record337, slope-30-115-near-old | Value |
|---|---|
| Ghost before | (-18.486170,1.408951,131.503342) |
| KCC requested | (-0.589489,-0.000034981,+0.003631592) |
| Forward normal | (0.964566469,0.263840288,0.000127155) |
| Dot | -0.568610190 |
| Callback current | (-18.486170,1.443951,131.503342) |
| Callback target | (-18.527197,1.593939,131.507050) |
| Ghost after | (-18.527197,1.558939,131.507050) |

Formula matches within float rounding. RequestedY is negative but ghostΔY is
+0.149987. PreStep and callback do not move it; step-up adds0.035 and down
removes it, leaving projection's net rise. EveryY>2 update in both large-ascent
traces had zero preStep ghostdelta and unchanged callback positions. This
localizes those rises, without proving no penetration recovery/tunneling elsewhere.
Movement-only seq335 already requestedY+0.286139; projection produced+0.375056.
Thus positiveY does not always originate inside Bullet. Upstream terrain feedback
was **PROBABLE**, exact writer not yet traced. Both captures had zero246.
Classification: original KCC response amplified by Sprint displacement, with
start-sensitive access to the surface, not a diagnostic vertical patch.

### Rejected post-contact candidate

`--suppress-on-contact` latched at forward callback72ADDB, after projection,
suppressing subsequent movement/animation factors; reset required zeroXYZ
request. It was explicitly diagnostic, not production.
`slope-fallback-115-1` started(-8.124241,1.4,131.625809),4s input,20s capture
covering≈first3s but not complete release;600updates,no overflow/conflict.
First latch seq541:ghostY1.407321→1.716587,requestedY+0.209700,
normal(0.964572966,0.263816118,0.000127158),fraction0.104247.
Latch states:540false/false,1false/true,59true/true. Fifty-two suppressed
updates still hadY>2;maxY4.656038,maxΔY0.309267. Later poll showed original
parameter0.169377014/rate1 atY1.818106, versus boosted0.194783568/rate1.15 before.
Walk2 remained unchanged; no special calls.

**FAIL:** suppression worked but did not prevent ascent after entry. The125
attempt failedFF/FE before installation and was excluded. Release/lifecycle were
not validated in the truncated run. **NOT READY**, next blocker prevention before
ordinary ascending submission, not arbitrary factor reduction. Cleanup restored
vptrs14080AE08/140879BD0/140822AE8,closed game,pad reset/disconnect,fps:null,
mods and SK services. Self-checks/Python/TOML/diff/hash passed;72B3C0 signature
was unique. Signed commit initially failed1Password; staged state was preserved.

## COLLISION-SLOPE-02 — 2026-10-09

### Native predicate and pre-projection gate

**CONFIRMED static:**72A570 stores angleKCC+34, calls importedcosf6EAB98,
stores cosine+38. StepDown72A7E1 reads it. Closest callback729CB0 rejects at
729DA5/729DA8 when `threshold > dot(up,world_normal)`; equality passes. Forward
sweep threshold is0. This differs from special-action9FDC=50. Runtime up axis E8=1,
angle0.0182770453393,cosine0.999832987785; historicalNy≈0.2638 is non-walkable
under the native criterion. No conventional degree threshold was substituted.

New hit data exists after72AC99; fraction is compared with1 at72ACAD. Normal,
object,fraction,target/current are available before72ACC8. Earlier recovery
72AB3C instead consumes cachedD0 whenC0!=0 and normalized-direction dot>0.

`pre_projection.py`,used by `slope_trace --pre-projection`, relocates private
playerStep/forward copies behind the verified KCC instance vtable. Gate only
72ACC8, not72AB3C. Guards include current player/KCC/physicsID,FF/FE,F8A6=1,
F8AD=0,current owner/controller/channel,clip122; ID was freshly resolved8, not
hardcoded10. On valid non-walkable new hit with incoming dotnormal<0 it latches
and divides target-current once if9F24 equals the boosted run value. Original
projection receives that target. Producer/animation suppress later factors.
A pass without a qualifying new hit releases, ignoring cached recovery.

The12-sample flat comparison at-10<X<-8.8,Y1.4 had vector Y0 and
vectorX/producer_dt/factor=-10.1624334..-10.1624244; normalized Z0.0624586..0.0625977.
This supports XZ scaling on flat ground, not blindly dividing terrain-producedY.
The vanilla-equivalent vector was reconstructed, not atomically preserved.
Trace includes incoming/equivalent/extra/passed/projected,normal,fraction,dot,
cosine,eligibility,latch and sequence/thread. In1.25 `passed` includes world
target-store rounding; in1.15 it is the pre-store quotient. Polls are separate.
Private code lacks unwind registration: bounded diagnostic, not production ABI/
concurrency/lifecycle validation. Two pre-hook allocation failures were excluded;
near-code and ring allocations were subsequently separated.

### Rastoria trials

Same slab visually verified,pad(-0.5,0.8660254),buttons0,4s,consumed(-65,-111),
world-X/small+Z, camera unchanged, requested cap30, no new external FPS measure.
Baseline3E2D712B,pad-only resets,30s captures,nonidentical starts.

| Capture | Move/animation | Ghost startXYZ | MaxY | Deboost events |
|---|---|---|---:|---:|
| preproj-vanilla-02 | 1/1 | (-7.177174,1.4,131.747375) | 1.595798 | 0 |
| preproj-115-01 | 1.15/1 | (-7.693682,1.4,131.640152) | 1.604610 | 3 |
| preproj-vanilla-03 | 1/1 | (-7.310448,1.4,131.632523) | 1.593651 | 0 |
| preproj-115-02 | 1.15/1 | (-7.349705,1.4,131.632217) | 1.595754 | 2 |
| preproj-vanilla-04 | 1/1 | (-7.238592,1.4,131.640228) | 1.596203 | 0 |
| preproj-115-03 | 1.15/1 | (-7.249524,1.4,131.641937) | 1.595841 | 2 |
| preproj-125-01 | 1.25/1.25 | (-7.084576,1.4,131.642502) | 1.596424 | 2 |
| preproj-vanilla-05 | 1/1 | (-7.574902,1.4,131.640060) | 1.596197 | 0 |
| preproj-125-02 | 1.25/1.25 | (-6.857341,1.4,131.642487) | **12.982490** | 11 |

All completed restored,zero conflicts/overflow/special calls. Playback1.25 outside
latch and1 inside;walk2 preserved. Three stable1.15 trials did not justify a safe
default. Vanilla02 preceded ID-filter correction and had eligibility false/no
deboost; later controls were eligible but untouched. Vanilla01 had no consumed
pad motion and was excluded.

### First bad update

`preproj-125-02` seq481/thread50540:ghostY1.413463235→1.844524145,
ΔY+0.431060910;seq483 exceeds2. KCC requested already
(-0.387470275,+0.355826199,+0.002380371). PreStep ghost became
(-18.611001968,1.414867520,131.490646362);playerStep ended
(-18.728504181,1.844524145,131.493072510),delta
(-0.117502213,+0.429656625,+0.002426147).
Latchfalse/false,appliedfalse,no72ACC8 or new forward callback.
CachedD0=(-0.964579582,-0.263792157,-0.000155674),C0=1.

**HIGH CONFIDENCE at this checkpoint:** original72AB3C recovery escaped the
new-hit gate. Requested dot cached normal=+0.279881385; reconstructed projection
(-0.117502406,+0.429656713,+0.002423941) matches playerStep within float rounding. It was
then an offline derivation, not a directly recorded recovery call. Internal
target/fraction were UNKNOWN; no new-hit fraction can be attributed to recovery.
Animation request122/rate1 at15.199551s and later idle19.196622s made clip122
at the bad update HIGH CONFIDENCE, not an atomic read. Last new hit seq463,
fraction0.500332475, had deboost/latch false→true; later release allowed boosted
production again. No evidence that the bad update had actually been deboosted.

**NOT READY:** cover cached recovery and preserve original contribution before
positive requestedY production. No alternate projection,Y clamp,gravity or ghost
writes were added. Testing stopped after failure; no third125 run or subordinate
sanity. Cleanup/static checks passed and EXE hash remained unchanged. The prior
signed commit succeeded as3465c26;SLOPE-01/02 remained separate newer work.

## COLLISION-SLOPE-03 — 2026-10-09

### Native cached recovery and lifecycle

**CONFIRMED static:** preStep72A160 resets C0 at72A1A0. Contact scans consider
negative distances and retain the deepest contact's signed normal at D0
(72A36C). Sign depends on ghost identity in the manifold (+1/-1), not Y sign.
Penetrating contacts add signed-normal×negative-distance corrections to current+70;
72A440 sets C0=1 when penetration was corrected. There are up to five passes;
a later clear pass does not clear an already-set flag. Ghost is updated, then
current/target aligned to it. D0 is not cleared when C0 resets.

Therefore C0 means **penetration corrected in this preStep**, not ground, new
sweep or persistent dangerous-surface memory. A stale normal alone does not
prove active contact. Forward72A9D0 sets target+90=current+displacement;
72AAF9 requires C0!=0. 72AB09..72AB2A dots normalized direction+60 with D0;
72AB2E/72AB32 skip<=0 or unordered. Positive dot calls72B3C0 at72AB3C with
RDX=&D0,XMM2=0,XMM3=1, modifying target+90. No new hit fraction exists.
The signed cached normal points inward; negative-distance correction moves out.
Positive dot means movement into that surface; away reverses it and skips.
For cached walkability use outward `-normal.Y`, not the new-forward-hit sign.
Away semantics were statically established; runtime release was not approved
because the candidate failed first.

### Direct recovery and original producer trace

`--pre-projection --cached-recovery` instruments only the private72AB3C callsite,
preserving original recovery. Records share physical sequence/thread and include
current/target before/after, requested+50, direction+60, C0/D0, dot, ghost after
and gameplay snapshots. Ghost after is correlated only when completion, sequence
and thread match; ring conflicts/overflows invalidate. The setter prefix saves
original XMM2, incoming target/current,9E20/9DF0/9E10 before perturbation. Latest producer
sequence is cross-thread correlation, not an atomic counterfactual vanilla
integrator. Existing integrated state is not a separately evaluated vanilla result.

`cached-trace-125-02`, seq299/thread20128 directly observed recovery with C0=1,
latch false, boosted parameter0.211721271:

| Field | Value |
|---|---|
| Requested | (-0.405292541,+0.322403222,-0.000228882) |
| Cached normal | (-0.964578271,-0.263796896,-0.000097704) |
| Requested dot normal | +0.305887431 |
| Current before | (-18.608367920,1.447212100,131.376174927) |
| Target before | (-19.013660431,1.769615293,131.375946045) |
| Target after | (-18.718608856,1.850307465,131.375976562) |
| Projected delta | (-0.110240936,+0.403095365,-0.000198364) |
| GhostY after | 1.815307498 |

Native0.035 vertical step accounts for target/ghost offset. This is direct
recovery evidence, superseding SLOPE-02's offline-only inference.

### Positive requestedY originates upstream

Setter target Y equaled current Y. At the first cited recovery, gameplay current
Y and integrated9DF0.Y were0.011796951, while target9E20/request9E10.Y were
0.684442341. A047=0. Extra Y was already present before KCC/preStep. Gameplay
feet and ghost center differ≈1.4; compare like coordinate systems. Static1E9980
preserves incoming target9E20 and parameter9F24; the ordinary caller builds
target from direction/current. 1F69B0 zeros direction Y if A047&4==0 and integrates
9DF0. A later conditional1F70A2 correction exists, but integrated Y stayed at
current Y in these records. 1F5240/1F5250 copies integration→9E10; virtual+178→
1F5B30 prepares the surface query. 1F5E15 can assign query height→target;
request paths include1F5E99 and ordinary A025=0 branch1F64DD..1F663D→164840,
component1 at9E10.

At this checkpoint surface preparation was **HIGH CONFIDENCE** as the first
additionalY source; exact internal store had not yet been instrumented. Boosted
XZ changes the query point before KCC. Preserving only the original parameter
does not preserve that geometric history; no recoveryY division or invented
`requested/factor` vanilla integration was used.

### Rejected preventive cached suppression

`--cached-suppress` checked C0!=0, outward normal non-walkable and incoming
target-current dot cached normal>0 before1E9980 multiplication. A shared latch
suppressed movement/animation. Forward release consulted cached state too.
Original recovery was unchanged; C0 was neither treated as ground nor written.
Same area/pad4s/cap30; direction approximately-X/small-Z this session. Numeric
yaw was not captured; pad resets gave nearby, nonidentical starts.

| Capture | Mode | StartXYZ | MaxY | Recoveries | Result |
|---|---|---|---:|---:|---|
| cached-trace-125-01 | Old gate | (-6.993392,1.4,132.793457) | 1.652868 | 0 | Wrong lane, excluded |
| cached-trace-125-02 | Old gate | (-8.114193,1.4,131.382248) | 8.210943 | 10 | Recovery/ascent reproduced |
| cached-suppress-125-01 | New candidate | (-8.099896,1.4,131.402527) | 14.217790 | 5 | FAIL, STOP |
| cached-vanilla-01 | Trace only | (-8.462970,1.4,131.444199) | 1.599308 | 0 | Nearby stable control |

Candidate producer15 had original parameter0.169377014, target/current Y0.011368990,
C0=1, normal(-0.964572906,-0.263816476,-0.000101893), latch false→true before
boost. Physical299 read that vanilla parameter, latch true, latest producer15.
Integrated Y remained0.011368990; target/request Y became0.076233149; KCC
requested Y+0.044765744; original projection Y+0.160773635, ghost after1.572506547.

| Physical sequence | Latest producer | Parameter | Latch | Ghost Y after |
|---:|---:|---:|---|---:|
| 299 | 15 | 0.169377014 | true | 1.572506547 |
| 301 | 16 | 0.169377014 | true | 1.684026837 |
| 303 | 17 | 0.169377014 | true | 1.894337177 |
| 309 | 20 | 0.169377014 | true | 2.074179411 |
| 311 | 21 | 0.169377014 | true | 2.291207075 |

Three consecutive suppressed producers still rose; the third recovery added
≈0.2103Y. Producer18 saw C0=0 and released; physical305 read boosted0.211721271
and crossed Y2. Later contact toggled the gate. The14.217790 peak includes
renewed boost, so it must not all be attributed to vanilla-parameter recovery.
Both inadequate pre-production suppression and unstable release were observed.
All four logs restored, zero conflicts/overflow/invalid, special calls0.
Animation polls were not atomic recovery reads; no recalibration. Vanilla
stopped near X-18.346 versus boosted first cached contact≈-18.61: history was
already different.

Deeper arrival/query/contact feedback was **PROBABLE**, exact state requiring
architecture change remained unknown. No tunneling label or normal/projection
fix was justified. **NOT READY:** preserve vanilla query/first-contact path,
rather than restoring1E9980 after reaching divergent state. No further candidate
or subordinate sanity was run. Cleanup restored all state; self-checks/Python/
TOML/diff/hash passed. Prior SLOPE-01/02 signed commit6db581b was preserved before
new SLOPE-03 work.

## COLLISION-SLOPE-04 — 2026-10-10

### Exact terrain writers

`terrain_trace.py` used private player-method copies with original calls, a
bounded 8192×512-byte ring and walk_trace restoration. It recorded producer,
thread, sequence, parameter, current, integration, requested/target, actual query
segment, hit Y/normal/index and physical ghost. Ordering is not cross-thread
frame atomicity.

**CONFIRMED static/runtime chain:** +168→20B2A0→1EAE70→1F69B0 produces +9DF0;
+170→259430→1F5240 copies integration at 1F5250, then calls +178→1F5B30 and
+180→1EA4E0. Primary query: 1F5CC0→31EE00; fallback: 1F5D2D. 31EED9→6CB920
uses a vertical segment from input Y+1.2 (observed height) to input Y-1000.
A negative engine index means failure; 31EF61 derives the Boolean result.
**1F5E15 writes target+9E20.Y; 1F663D→164840, component 1 in XMM1, then
16488F writes requested+9E10.Y.** The trace observed common caller 31EEDE and
engine index, not every primary/fallback distinction or final Boolean. Query
XZ can differ from requested XZ (maximum control error≈0.4508); use the recorded
segment.

| terrain-legacy-125-02,producer6 | Observation |
|---|---|
| Original/effective parameter | 0.169377014(3E2D712B)/0.211721271 |
| Current/integration Y | 0.281662345, no integration rise |
| Query start/end | (-19.023054,1.48166239,131.646225) / (-19.023054,-999.718323,131.646225) |
| HitY/index | 0.356889367/1 |
| Normal | (0.964573264,0.263815254,0.000096804) |
| seq1120,1F5E15 | TargetY0.281662345→0.356889367 |
| seq1121,1F663D | RequestY0.281662345→0.356889367,argument equals hitY |
| Flags | A0250,A04C1,A01E1,A0210,A0470 |
| seq1122,KCCrequest | (-0.574808061,+0.051066637,+0.003540039,0) |
| seq1123,ghostY | 1.681662440→1.875444174 |

The capture later reached Y=14.21778965. This identifies the exact writer; it is
not a new causal A/B comparison because it started already at contact, ghost
(-18.328770,1.40742218,131.623627). Legacy01 had no input/setter in its capture
window and was excluded.

### Architecture assessment

| Candidate | Result / limitation |
|---|---|
| A: extra physical substep | Feasible bounded diagnostic; original first wrapper, second physical step, owner sync observed. Duplicate physical side effects/lifecycle unvalidated. |
| B: extra after query, before wrapper | Preserves query point but lengthens first-contact displacement, retaining known projection risk; not adopted. |
| C: capsule preflight | Tested with A using native sweep/KCC shape, not a point ray. Does not replace slope terrain query. |
| D: spatial substeps | A implements vanilla plus remaining0.25 physically, without full gameplay duplication. Contact-history/ramp equivalence not yet proven. |

No broader Phyre metadata project was opened. `terrain-preserve-01` requested
Sprint but kept original walk 0.04343000054/run 0.169377014 before integration
and query. Same-producer parameter equality was CONFIRMED; preserving the first
query path for equal state was HIGH CONFIDENCE from static analysis. Different
starts are not paired, bit-identical runtime queries.

### Diagnostic A+C invariants

1. Save KCC requested+50; execute the original first 58D340.
2. Require entry E3=1, verified player, F8A6=1/F8AD=0, FF/FE, exact run bits
   3E2D712B; abs(requested Y)≤0.001 and first actual/requested XZ error≤0.0002
   per component.
3. Extra XZ=0.25×vanilla contribution; requested Y/W=0. No gameplay Y, target
   or ghost write.
4. Sweep 6F8890 from the ghost after the first step, with KCC shape+18, native
   callback 8C55C0/729CB0, self and native group/mask. Temporarily use the native
   forward margin, then restore it.
5. Only if there is no hit object, submit 72A5F0 and execute a second original
   58D340 with dt=0. The wrapper clears E3/E4. No second full gameplay update or
   additional dt.

The second step still runs native preStep/stepUp/stepDown/sync; absence of every
duplicate side effect was UNKNOWN. Accepted extras establish the no-hit branch,
but the initial trace did not record all rejection fractions/normals or every
special/recovery event. The animation getter remains player-channel/clip122
only: factor1.25 after an accepted extra, otherwise vanilla. The per-update DWORD
resets before the first step and is set on no hit; it is not a cached-contact
latch. Polls observed 1→1, 1→1.25 and 2→2, without proving atomic worker/lifecycle
safety. The first extra capture missed animation polls; walk_trace polling was
made independent of the submission logger.

### Anticamera trials

Historical slab, pad(-0.5,0.8660254), buttons0, 4s, unchanged camera, inverse
input for away. Requested cap30 before Steam restart, no external FPS measure,
bounded pad-only resets.

| Capture | Start XYZ | End XYZ | Max Y | Accepted extras |
|---|---|---|---:|---:|
| terrain-vanilla-01 | (-7.760714,1.4,131.441330) | (-18.304810,1.407419,131.623611) | 1.596209049 | 0 |
| terrain-preserve-01 | (-8.475770,1.4,131.635651) | (-18.322227,1.407422,131.623596) | 1.595162511 | 0 |
| terrain-extra-01 | (-8.552626,1.4,131.630219) | (-18.246811,1.407437,131.623596) | 1.595115423 | 7 |
| terrain-extra-02 | (-8.418660,1.4,131.637726) | (-18.427444,1.407436,131.623642) | **1.704176545** | 8 |
| terrain-extra-away-flat-01 | (-18.427444,1.407436,131.623642) | (12.037760,1.474658,131.000793) | 1.474796653 | 20 |
| terrain-vanilla-02 | (-7.967122,1.4,131.644440) | (-18.473705,1.407421,131.623611) | 1.594958544 | 0 |

Flat extra XZ/first vanilla displacement=0.2499992977..0.2500003559; actual extra
dY=0. The next gameplay current X matched the previous final ghost X exactly in
the away capture. Away accepted extras again, including producers19..28, without
sticky suppression. Vertical-eligibility fallback does not establish 25% Sprint
throughout slopes or average lane speed.

**Historical outlier:** terrain-extra-02, producer57, physical1854/1855 had no
extra. The original step moved ghost(-18.2563763,1.592821121,131.623611) to
(-18.2868328,1.704176545,131.623642), with vanilla parameter0.169377014.
Integration X changed -18.256376→-20.8814468 (delta≈-2.625), while Y=0.192821025
was unchanged. Query hit Y=0.00722324848, normal(0,0.999913,0.013187); KCC
request(-0.590133786,-0.041723691,+0.003631592,0). All eight preceding extras
had dY=0, maximum extra Y=1.404827. The peak was in the first native step, not
an extra substep. Usual integration delta was≈0.677; differing start/timing
prevent causal attribution of the≈0.108 excess over controls to Sprint.

**NOT READY:** query-fed Y source closed; separated flat extra/sync confirmed;
first-contact equivalence after extras unknown. No new latch, Y fix or subordinate
sanity test. Cleanup restored vptrs, closed the game, neutralized/disconnected
pad and restored fps:null, mods/Special K. Terrain/walk self-checks, Python,
TOML and diff/hash checks passed; EXE unchanged.

## COLLISION-SLOPE-05 — 2026-10-10

**NOT READY — F/UNKNOWN.** New vanilla/dry runs exceeded Y=1.704, so Ymax was
no longer a sufficient A+C regression signature. The narrower blocker was to
recapture integration X≈2.625 with the actual consumed 69B4C0 return and upstream
branch/scalars.

### Timing instrumentation and historical extra history

The bounded terrain ring expanded to 8192×1024 bytes. Private player-integrator/
getter observers preserved originals and all A+C/Y/collision/animation behavior.
The ordinary call is 1F6ADF→69B4C0; 1F6AE7 multiplies the return by9FE8. With
4E0=0, the parameter term is9F24+scalar*9F2C, then multiplied by the scalar and
target-current direction. A047&4==0 zeros direction Y. 1F6EA4→1AD750 normalizes;
1F6EC4 stores integration; later original branches can still modify it.

Records include in-event QPC/thread/sequence (10MHz, entry code verified), A63238/
A6323C/A63240/A63244, actual consumed return,9FE8/9F2C/4E0, parameter, direction,
integration/query and physical state/C0/D0/E0..EF before/after. Player cadence is
consecutive ordered player QPC, not same-thread gaps: workers rotate. Vanilla02's
old per-thread derived field was corrected offline using its recorded QPC.
The last-eight-extra history contains producer/physical sequence, QPC at second
wrapper entry, ghost before/after, extra, wrapper marker, count since previous
producer and logical distance. Derived serializer fields were added after capture
from existing before/after records.

Historical SLOPE-04 last extra: producer13/seq1327, ghost
(-17.35886574,1.40482700,131.52696228)→
(-17.52832413,1.40482700,131.52799988), requested
(-0.169458881,0,+0.001041412,0). Setter57/seq1846 was44 producers/519 sequences
later; bad step1854/1855. Exact historical elapsed time is UNKNOWN (no QPC then);
44/15 is not a measurement. Assuming the ordinary branch/9FE8=1/9F2C=0, the
2.625 delta would require return≈15.499/app dt≈258.3ms. **Conditional inference,
not a measured historical return.**

### Controlled series and first contact

Same Anticamera/pad4s/camera/cap30, no external FPS measure, pad-only resets.
New direction≈(-0.99999982,0,-0.00058), unlike historical small+Z: not an exact
replay. The first vanilla capture also hit an edge before the main face.

| Capture | Start XYZ | Max abs integration X | Max Y | Extras/preflight |
|---|---|---:|---:|---:|
| interval-vanilla-02 | (-8.379351,1.4,131.877548) | 0.687431 | 1.659388 | 0/0 |
| interval-vanilla-03 | (-7.373043,1.4,131.592056) | 0.695817 | 1.901794 | 0/0 |
| interval-vanilla-04 | (-7.392611,1.4,131.613373) | 0.692215 | **5.235761** | 0/0 |
| interval-preserve-01 | (-7.655859,1.4,131.637955) | 0.701435 | 1.597311 | 0/0 |
| interval-dry-01 | (-7.414088,1.4,131.599121) | 0.696627 | **5.793885** | 0/14 |
| interval-extra-01 | (-7.404352,1.4,131.621765) | 0.687836 | 1.594011 | 11/11 |
| interval-extra-02 | (-7.955672,1.4,131.638351) | 0.701206 | 1.597913 | 10/10 |

Vanilla01 was an excluded idle 1,620-event smoke test. Seven valid captures had
3,733–4,488 events, zero overflow, empty stderr and successful restoration. High
vanilla/dry Y is not A+C failure. Offline first contact means the first original
72ADDB callback with main-face normal≈(0.96457,0.26381,0), not a new runtime filter.

| Capture | Producer/physical/callback sequence | Integration ΔX | Consumed return | Requested Y | Ghost Y before→after |
|---|---|---:|---:|---:|---|
| vanilla02 | 18/1540/1542 | -0.675829 | 3.990084 | +0.00010213 | 1.408042→1.553586 |
| vanilla03 | 19/1516/1518 | -0.677530 | 4.000134 | -0.00003618 | 1.407886→1.543397 |
| vanilla04 | 19/1552/1554 | -0.680275 | 4.016340 | -0.00003373 | 1.407605→1.534800 |
| preserve01 | 18/1547/1549 | -0.675722 | 3.989454 | +0.00011549 | 1.407312→1.573834 |
| dry01 | 19/1890/1893 | -0.679916 | 4.014222 | -0.00003003 | 1.407790→1.529511 |
| extra01 | 16/1862/1865 | -0.676996 | 3.996984 | +0.00006070 | 1.407388→1.507360 |
| extra02 | 15/1832/1835 | -0.677471 | 3.999786 | +0.00002730 | 1.407299→1.579713 |

Query start Y=current feet Y+1.2, hit Y=0.007326..0.008162. Corresponding query X:
-18.823053/-18.870796/-18.906540/-18.468306/-18.927361/-18.719656/-18.475502;
Z=131.568573..131.631958. First preStep C0 was0 before/after all these contacts;
D0 could already differ. No new direct72AB3C entry trace or semantics was claimed.

### Timing and second-wrapper assessment

All58 verified run producers per trial had9FE8=1,9F2C=0,4E0=0. The product
normalized direction×parameter×consumed return×9FE8 matched integration delta
within≈1e-6X, zeroY,8e-6Z. The getter reads a scalar; it does not accumulate intervals.

| Condition | Consumed return range | Player QPC interval ms |
|---|---|---|
| Three vanilla | 3.887–4.109 | 64.446–68.684 |
| Preserve | 3.864–4.141 | 65.439–68.044 |
| Dryrun | 3.891–4.113 | 64.791–68.089 |
| TwoA+C | 3.871–4.140 | 65.359–68.829 |

The maximum return occurred in preserve without extras, app dt≈69.021ms. No2.6
delta appeared; this small series does not prove vanilla cannot produce it. No
A+C timing accumulation or cadence slowdown was observed. Dry run executes
eligibility/calculation/sweep/log but neither72A5F0 nor second58D340:14 preflights,
one hit, no extra, rates1→1/2→2. Its ascent shows the second step is unnecessary
for that new ascent, not that preflight caused the historical outlier. Vanilla04
also ascended without preflight. An uninstrumented bit-identical replay did not
exclude common instrumentation, so causeD was not established.

The second wrapper modifies KCC current/target, syncs player current and changes
E3 from1→0. Requested/direction retain the extra until the next submission.
Extra02 producers7/8 also changed C0/D0 despite clear preflight: physical state
can differ. Requested extra Y=0; one actual dY=-0.000018835 was native correction,
others zero. No counter/dt/normal compensation. Extra01's last pre-contact extra
was producer15/seq1847, X-18.242651→-18.412027,66.235ms before producer16;
extra02's was13/1801,X-17.277948→-17.447330,132.695ms before producer15.
Subsequent cadence remained in the vanilla range, without proving identical
contact history. Animation coupling was unchanged:1→1/1→1.25/2→2 observed.

### Decision and cleanup

The historical1.704 peak is numerically compatible with new vanilla variation,
but the historical producer remains **F/UNKNOWN**, not A(vanilla-equivalent),
B(A+C timing), C(contact-state cause) or D(instrumentation/preflight cause).
Candidate A was neither approved nor causally rejected. No spatial cutoff was
added:44 producers without extras already preceded the peak and would not
identify its dt. No lower-factor workaround. The SLOPE-04 signed-commit retry
failed1Password; index preserved, SLOPE-05 separate. Cleanup restored vptrs,
closed game/pages, reset/disconnected pad and restored fps:null/mods/Special K.
Self-checks, Python, TOML, both diff checks and EXE hash passed. No proprietary
files were committed.

## COLLISION-SLOPE-06 — 2026-10-11

**Checkpoint decision: NOT READY — F/UNKNOWN.** The bounded series completed:
10 valid runs per V/D/A, no timing/integration trigger. This session did not
unilaterally remove the historical blocker or approve A+C.

### Exact 69B4C0 source

**CONFIRMED static:**69B4C0..69B4E2 has two returns, no other source, return XMM0.
The byte comparison is C82FAC==1, not generic nonzero.

| Condition | Instructions | Source | Classification |
|---|---|---|---|
| C82FAC==1 | Load69B4C9,multiply69B4D1,ret69B4D9 | A63248×float32(60),constant803C3C | FIXED/ALTERNATE |
| C82FAC!=1 | Load69B4DA,ret69B4E2 | A63240 | NORMAL_DT |

The getter does not directly read A63238/A6323C/A63244. Flag writers/full meaning
are outside scope; the alternate branch was not exercised live.

### Bounded anomaly capture

`outlier_trace.py` reuses unchanged A+C: extra0.25XZ/Y0, native preflight,
second-wrapper dt0, eligibility, first vanilla step and animation coupling.
V has no preflight/extra; D performs eligibility/preflight/logging without a
second step; A performs current A+C. The private producer remaps callsite1F6ADF
to an instrumented getter copy with the same comparison, one selected-source
read/multiplication and the actual consumed XMM0. No global getter or timing
source is patched/written. The same-producer record contains QPC/thread,
A63238..A63248, C82FAC, branch, selected source, return,9FE8/9F2C/4E0,
parameter, target/current, normalized direction and integration before/after.
The counter advances at integration stage2, including idle, not only setter
calls. Getter/integration share a thread; cross-worker physical/latest-producer
correlation is not atomicity.

Rolling history:64 before+trigger+16 after, frozen host copy after the post-window.
Diagnostic-only trigger:abs(integrationΔX)>1 or consumed return>6. The last8 extras
retain producer/physical sequence/QPC/ghost/displacement/preflight/second wrapper.
Self-check verifies both thresholds, the81-producer window, freeze and ring wrap.
Live freeze is untested because no event triggered.

### Thirty-run series

Historical Anticamera slab, pad(-0.5,0.8660254), buttons0,4s, axes(-16384,28377),
camera unchanged, initial normalized world direction≈(-0.999981,0,+0.006155).
Each capture lasted18s, with≈6s initial prehistory, pad-only resets and requested
cap30 before launch; no external FPS measure. Order V A V D A D repeated5 times.

| Condition | Runs | Producers with consumed getter | Max return | Max abs ΔX | Max ghost Y | Extras/preflight |
|---|---:|---:|---:|---:|---:|---:|
| V | 10 | 620 | 4.193082 | 0.710197 | 1.600238 | 0/0 |
| D | 10 | 620 | 4.251618 | 0.720112 | 1.602817 | 0/110 |
| A | 10 | 622 | 4.162686 | 0.701635 | 1.596872 | 95/95 |

There were8,100 native integration entries,1,862 consumed-getter producers and
97,918 events. All returns were NORMAL_DT, C82FAC=0,9FE8=1,9F2C=0,4E0=0.
All1,862 fit normalized direction×parameter×consumed return×9FE8, with maximum
XYZ float reconstruction error7.63e-6u. The consumed return equaled recorded
A63240 source.

| Source | Min | Max |
|---|---:|---:|
| A63238 seconds | 0.062596798 | 0.070860296 |
| A6323C | 14.112275 | 15.975258 |
| A63240 | 3.755808 | 4.251618 |
| A63244 | 60 | 60 |
| A63248 | 1 | 1 |

Moving-producer QPC intervals were52.0071..81.2727ms; all integration entries,
including idle,5.5387..203.2224ms. Four natural>100ms gaps (D02 producers40/174,
V08 producers152/154) had parameter0, deltaXYZ0 and no getter call: not evidence
of high moving dt. No stall was induced.

| Condition | Start X range | Start Y | Start Z range |
|---|---|---|---|
| V | -7.747937..-7.561017 | 1.4 | 131.369110..131.396942 |
| D | -7.738849..-7.547272 | 1.4 | 131.386841..131.404114 |
| A | -7.699688..-7.412622 | 1.4 | 131.389297..131.404449 |

Local ignored files outlier30-{V,D,A}-{01..10}.jsonl retain individual starts;
all30 restored with empty stderr. Bounded resets and a small series do not prove
absolute contact equivalence. Excluded: initial smoke with setter-only counter
(corrected before the formal series), cap60 smoke, navigation/low-stick resets.
Final serializer idle-scalar/preflight-history extensions passed self-check
without another live run beyond the bounded limit.

### Classification

No event classifies the historical outlier as T1 normal-dt spike, T2 alternate
branch, U1 upstream branch, U2 downstream mutation, C A+C-induced state or
V vanilla-equivalent. **F/UNKNOWN** remains; Ymax was not a gate. SLOPE-05 vanilla/
dry ascents remain valid even though not reproduced here. The session stopped
at its limit, without new filters, latches, timing compensation, production
Sprint, Audio or subordinate sanity tests. Cleanup restored vptrs, closed game/
pages, neutralized/disconnected pad and restored fps:null/mods/Special K.
Self-checks, Python, TOML, staged/unstaged diff and hash checks passed. Another
signed SLOPE-04 retry failed1Password; index and separable SLOPE-05/06 were preserved.

## COLLISION-SLOPE-07 — Diagnostic sanity suite

October17–19. **Checkpoint decision: NOT READY — accepted post-reload lifecycle
run incomplete.** User Escape stopped Computer Use before the final reload;
not a proven A+C failure. S1–S8 each have one vanilla control and two A+C runs.
Research later closed the historical blocker pragmatically without claiming to
have classified its cause.

### Method

Virtual pad through Steam, pad-only resets, bounded nonidentical starts, camera
fixed per comparison, right stick only during S2 scouting. `sanity_trace.py`
adds bounded Python summaries of SLOPE-06 records without changing native shims,
A+C, eligibility or catcher. The250ms QPC windows/E3E4 polls are not atomic
frames; native records supply step/delta counts. First gameplay vanilla, extra
XZ0.25, requested Y0, preflight, second-wrapper dt0 and animation1.25 only on
accepted extras remain unchanged. No suppression filter, latch or Y clamp.

Unchanged source SHA-256 at this checkpoint:

- terrain_trace.py:82e399598bcf51a4137db60f157c4f3b68008eea720bbd6f54c58add85c2e31b
- walk_trace.py:1d2280a947ed62c6545bd61dd2490bc4015e4b2ac093e2a268ae913e8906d130
- outlier_trace.py:42456313ba01679a7acf4198fe1e2e777c4fa51caee147266404587f70197a44

No new FPS override:NVAPI-166 failed before mutation. V/A used the same unlimited
profile without external FPS measurement. The October18 process was absent on
October19; the new player level/session required a new S6 control. No causal
crash claim was made for the exit between sessions.

### Geometry and inputs

All buttons0; each input duration denotes one pulse.

| Sanity | Geometry | Pad / duration | Result |
|---|---|---|---|
| S1 | Poggio Phoeniath, ordinary slope | (-0.5,0.8660254),4s | PASS, progress/vertical fallback |
| S2 | Foresta Grilim, three stone steps before circular building | (-0.70710678,0.70710678),1.5s | Limited PASS, few eligible extras |
| S3 | Steep entrance side | (-0.96365,-0.26717),1s | PASS, stop/preflight hit |
| S4 | Oblique curved entrance side | (-0.871,0.4913),0.7s | PASS, sliding/transient native correction |
| S5 | Short near-parallel side, initial distance≈1.4u | (-0.26717,0.96365),0.7s | PASS, extras generally accepted |
| S6 | Away from wall, new session/camera | (-1,0),0.35s | PASS, no observed sticky state |
| S7 | Grilim landing, stop/start | (0,-1),(0,1),twice,0.6s each | PASS, several-second pauses |
| S8 | Landing, short consecutive reversals | (0,-1),(0,1),(-0.25,-0.9682458),(0.25,0.9682458),0.3s each | PASS, current-request alignment |

World directions:S1≈(-0.4995,0,-0.8663), S2≈(-0.872,0,+0.489), S3≈+Z,
S4≈(-X,+Z), S5≈-X, S6≈-Z. The new S7/S8 camera maps y=-1 to-X and x=1 to+Z.
S8 neutral intervals between consecutive commands were<1ms in the pad log,
unlike S7's long pauses.

Local ignored s7-<run>.jsonl/.err files retain full precision. A/H below means
attempts/accepted/preflight hits; DX=maxabs integrationΔX; path=sum of native XZ
steps, excluding outer-wrapper double counting. Return/DX maxima may occur in
different producers.

| Run | StartXYZ | MinY,MaxY | Maxreturn | MaxDX | A/H | PathXZ |
|---|---|---|---:|---:|---|---:|
| slope-scout(S1V) | (254.4730,1.4000,-62.3247) | 1.3563,2.9610 | 0.578118 | 0.048904 | 0/0/0 | 39.5566 |
| S1-A03 | (254.3513,1.4000,-62.3069) | 1.3622,2.9634 | 0.639714 | 0.054123 | 296/296/0 | 43.6322 |
| S1-A04 | (254.3053,1.4000,-62.1332) | 1.3689,2.9701 | 0.542310 | 0.045883 | 292/292/0 | 43.5730 |
| S2-Grilim-V01 | (-643.1719,26.0906,-390.0454) | 26.0906,30.7047 | 0.468780 | 0.069214 | 0/0/0 | 14.1101 |
| S2-Grilim-A01 | (-643.1484,26.0822,-390.0587) | 26.0822,30.7047 | 0.503694 | 0.074402 | 12/12/0 | 14.2308 |
| S2-Grilim-A02 | (-643.1863,26.0958,-390.0372) | 26.0958,30.7047 | 0.753912 | 0.111328 | 11/11/0 | 14.2586 |
| S3-Grilim-V02 | (-655.6834,30.7047,-384.2018) | 30.7046,30.7047 | 0.469938 | 0.000427 | 0/0/0 | 1.4416 |
| S3-Grilim-A02 | (-655.7028,30.7047,-384.1914) | 30.7045,30.7047 | 1.280448 | 0.001343 | 17/16/1 | 1.4323 |
| S3-Grilim-A03 | (-655.7237,30.7047,-384.1810) | 30.7046,30.7047 | 0.397068 | 0.000427 | 19/18/1 | 1.4316 |
| S4-Grilim-V01 | (-655.7379,30.7047,-382.7907) | 30.7047,30.7047 | 0.432660 | 0.045105 | 0/0/0 | 5.2375 |
| S4-Grilim-A01 | (-655.8032,30.7047,-382.9567) | 30.7047,30.7048 | 0.366018 | 0.033447 | 82/81/1 | 6.2231 |
| S4-Grilim-A02 | (-656.1171,30.7047,-382.8100) | 30.7047,30.7070 | 0.400404 | 0.047974 | 81/81/0 | 6.3525 |
| S5-Grilim-V01 | (-655.5954,30.7047,-384.2409) | 30.7047,30.7047 | 0.357774 | 0.060608 | 0/0/0 | 5.9896 |
| S5-Grilim-A01 | (-655.6562,30.7047,-384.2078) | 30.7047,30.7047 | 0.367596 | 0.062195 | 132/132/0 | 7.4083 |
| S5-Grilim-A02 | (-655.6049,30.7047,-384.1674) | 30.7047,30.7047 | 0.415242 | 0.070312 | 130/130/0 | 7.3281 |
| S6-new-V01 | (-656.4811,30.7046,-382.7946) | 30.7046,30.7047 | 0.971724 | 0.000000 | 0/0/0 | 2.3924 |
| S6-new-A01 | (-656.4695,30.7046,-382.8205) | 30.7046,30.7047 | 0.645342 | 0.000000 | 25/24/1 | 2.4164 |
| S6-new-A02 | (-656.4557,30.7046,-382.8012) | 30.7046,30.7047 | 0.543624 | 0.000000 | 25/25/0 | 2.3934 |
| S7-V01 | (-656.4532,30.7046,-385.1921) | 30.7046,30.7047 | 1.605942 | 0.272034 | 0/0/0 | 20.1926 |
| S7-A01 | (-656.3318,30.7047,-385.1921) | 30.7047,30.7047 | 0.834144 | 0.141296 | 259/259/0 | 24.7756 |
| S7-A02 | (-656.2341,30.7047,-385.1921) | 30.7047,30.7047 | 0.711588 | 0.120544 | 269/269/0 | 24.6694 |
| S8-short-V01 | (-659.8947,30.7047,-384.7182) | 30.7047,30.7047 | 0.517686 | 0.085815 | 0/0/0 | 11.2036 |
| S8-short-A01 | (-659.8699,30.7047,-384.8248) | 30.7047,30.7047 | 0.707940 | 0.092773 | 159/159/0 | 13.9106 |
| S8-short-A02 | (-659.8677,30.7047,-384.9460) | 30.7047,30.7047 | 0.684918 | 0.090149 | 165/165/0 | 13.8056 |

### Interpretation and coverage limits

S1 progress is≈10% greater, not25% throughout: unchanged vertical eligibility
excludes many steps. First-native-step maximum dY≈0.08 also appears in vanilla
return reset02 on that terrain; surface-normal up dot reaches≈0.841, without
persistent vertical accumulation.

S2 crosses the visually identified three steps and reaches the same landing,
without anomalous double step, blockage or persistent difference. Only12/11
extras were accepted, actual dY0: functional vanilla fallback, not25% boost up
all stairs. Earlier steps/lowsteps scouting did not count as S2.

S3 stops near Z=-382.79; each A approach has one preflight hit rejecting the
extra, normal≈(0.00513,-0.00104,-0.999986), no observed ascent/penetration.
Already-contact V01/A01 are supporting captures, not replacements for approaches.

S4 preserves sliding. In A02 one requested-Y0 extra has actual dY+0.002244949,
exactly undone by the next native step's -0.002244949. Not all actual extra Y
is zero. S5 path increases22–24% without hits; mere wall proximity does not
suppress extras. A curved wall/short segment does not validate a long straight wall.

S6 extras resume away without reset: first A has one hit then24 accepted;
second25 accepted. No promise of extras during initial walk/vertical ineligibility.

S7 has four movement episodes; intervening/final windows have zero extras/path,
final requested0, no residual second wrapper. E3/E4 polls(0,0)/(1,0) also occur
vanilla; no new semantics. Getter1→1/1→1.25/2→2, no animation recalibration.
After S8, current/integrated XZ match ghost, usual1.4Y offset, requested0,
E3/E4(0,0), original rate1. The minimum dot between extra XZ and correlated first
request is≈1 in new S6–S8 A runs: no observed opposite-extra reuse, not proof of
full atomic gameplay synchronization.

Excluded:S1A01 ended before pulse, A02 lost focus, initial flat baseline;
camera/mouse-attack scouting; old October18 S6V replaced by new control; long S8
reversals with differing contact/space and S8-A01 descending off the landing.
Formal S8 uses only the short series.

### Catcher and partial lifecycle

The24 formal runs contain6,533 consumed-return producers,49,205 groups including
idle,567,405 events,1,974 extra attempts,1,970 accepted and4 preflight hits.
Max return1.605942, maxabs DX0.272034, all NORMAL_DT, no trigger/freeze. Scout
files also have no trigger. All formal records restored with empty stderr.
Diagnostic thresholds1/6 are not Sprint policy.

After stopping at Grilim, original vptrs were verified before travel. Fast travel
to Poggio Phoeniath, fresh scan/resolve, no hooks across transition (PID72088):

| Object | Before | After |
|---|---|---|
| Unique CChrPc | 218AE890 | 218AE890 |
| Physics ID | 4714 | 27872 |
| Wrapper | 2041F120 | 2034F0B0 |
| KCC | 825772C0 | 828FE670 |
| Animation channel | 268B3990 | 26881170 |

Controllers/ID/channel were freshly acquired; old addresses were not reused.
Original vptrs14080AE08/140879BD0/140822AE8. This validates teardown/reacquisition,
not persistent hooking during travel, respawn/combat/town. Lifecycle walk04 used
virtual stick0.75, path2.640942, rate2→2, zero extras. Run-V02/flat-approach
showed vanilla motion post-reload; no-motion/focus-loss captures were excluded.
Later selector1/FE, lifecycle-A-approved original rate1.558268 and zero extras
is not an effective A+C test. No causal claim about travel/weapons/second step.

Only remaining gate: accepted extra plus idle tail on reacquired FF/FE instances.
User stop interrupted the planned reload; not a proven movement failure.
**NOT READY at checkpoint.** Historical outlier remained UNKNOWN. No further
Computer Use after stop. Cleanup closed game/pad/pages and restored mods/Special K.
Five-tool self-checks, Python, TOML, diff/index/hash checks passed; research index
SHA ec8c6d3c459f504050d81cb7796d636176f6cc6d112ed454a31f05a2c092af3a.
NVAPI-166 prevented limiter read before mutation; no override created and no
newly verified driver fps:null claim. No commits/signing requests; staging preserved.

## COLLISION-SLOPE-07B — Lifecycle Closeout (2026-10-20)

**READY FOR SPRINT IMPLEMENTATION.**
**COLLISION-SLOPE: CLOSED pragmatically.**
**Historical integration outlier: UNKNOWN, not reproduced.**

Readiness for a first implementation, not a production-safety demonstration.
S1–S8 were not repeated; their limits and SLOPE-06 remain. A+C, guards,
preflight, second-wrapper dt0, catcher and animation coupling were unchanged.

### Normal context recovery and fresh identities

Normal Steam Continue, then in-game fast travel from Passo Trie Modragal to
Poggio Phoeniath. No selector/run-flag/parameter/clip/position/physics-ID writes,
no hooks during travel. Fresh CChrPc scan/physics lookup after load and before
installation (PID52380):

| Object | Before travel | After travel / both A+C runs |
|---|---|---|
| Player | 21928890 | 21928890 |
| Physics ID | 10 | 51 |
| Wrapper | 204C84B0 | 20559180 |
| KCC | 335D5D80 | 34CA8F70 |
| Animation channel | 26972320 | 2699F140 |

Current owner268F7DE0, animation controller269549C0; FF/FE before/after travel
and tests. An unchanged player does not mean controller reuse: new wrapper,
KCC, ID and channel were reacquired. Original vptrs14080AE08/140879BD0/140822AE8
before/after instrumentation. Pad was initially not consumed; CONTROL Resonant
was closed with Alt+F4 after explicit user authorization, then SAOHR restarted
through Steam with the virtual pad already connected. A/Start worked. This
sequence fixed the operational obstacle without proving the other app caused it.

### Two post-travel confirmations

Bounded captures in ignored scratch/slope07b-A01.jsonl/A02.jsonl. Short vanilla
approach on a clear path, camera unchanged, pad buttons0,X0,Y+1 for1.2s(A01),
Y-1 for1s(A02), automatic neutral release.

| Evidence | A01 | A02 |
|---|---:|---:|
| Capture duration | 25s | 30s |
| Consumed-return producers | 249 | 195 |
| Native events | 60,346 | 69,529 |
| Preflight / actually applied extras | 216/216 | 165/165 |
| Preflight hits | 0 | 0 |
| Extra actual ΔY min/max | 0/0 | 0/0 |
| Minimum XZ alignment | 1.0 | 1.0 |
| Ghost Y min/max | 1.397217/1.400000 | 1.400000/1.400000 |
| Max consumed return | 0.425214 | 0.648882 |
| Max abs integration X | 0 | 0 |
| Producer QPC interval | 3.959–14.021ms | 3.926–18.997ms |
| Getter1→1.25 observations | 90 | 73 |
| Walk2→2 observations | 14 | 14 |
| No-extra idle tail | 15.438s | 20.697s |
| Catcher trigger/frozen | None/false | None/false |

A01 ghost(254.473022,1.397217,-52.236282)→(254.473022,1.4,-65.914040).
A02 starts there and ends(254.473022,1.4,-54.654266). Maximum integration X0
reflects the±Z direction, not a new historical X-outlier test. All returns NORMAL_DT.

**Direct witness A01:** producer1746, physical thread7472, seq21084 vanilla request
(0,+0.000014424324,-0.052864074707);seq21087extra
(0,0,-0.013216018677). Extra ghost(254.473022,1.398953,-52.715630)→
(254.473022,1.398953,-52.728844).
**Direct witness A02:** producer1761, same thread, seq19491 vanilla
(0,0,+0.057754520327);seq19494extra(0,0,+0.014438630082).
Ghost(254.473022,1.4,-65.436165)→(254.473022,1.4,-65.421722).
Both requested extra XZ vectors are exactly0.25×recorded vanilla contribution,
Y0, with real displacement observed. Producer parameter remains0.16937701404094696.

Getter1.25 traversed unchanged guards: current physics51/owner/controller/channel,
actual channel instance, FF/FE, F8A6=1/F8AD=0, vanilla parameter, original return1,
clip122 with rechecked index and accepted-extra gate. This is native-branch proof,
not atomic polling with each physical step. Unchanged1→1/walk2→2 were recorded.
No new special action was provoked; unchanged other-clip exclusions were not retested.
Final FF/FE,F8A6=0,F8AD=0,clip0,channel rate1; idle tails had zero extras.
No catcher, crash or anomalous movement observed. An auxiliary poll rejected the
temporary player vptr because original-only resolve was used: validator error,
not stale reuse, and its data was not run evidence. The original resolver passed
after restoration, confirming current identities.

### Cleanup, limits and decision

Only collector change: a bounded first extra_physical witness with self-check;
no native/A+C changes. Both captures restored, empty stderr, original vptrs
reread before normal game exit. Pad neutral/reset/disconnect; mods active and
SK services restored; pages ended with the process, no EXE/CPK writes/drivers.
No FPS override created; NVAPI-166 again prevented driver read, so no newly
verified fps:null. Five-tool self-checks, Python, TOML and diff/index checks
passed; EXE and research-index hashes unchanged. Terrain/walk/outlier/pad
sources were unchanged during07B.

**Lifecycle gate closed within these limits.** Town/combat, concurrent production
lifecycle and production-safety validation remained outside approval. No Audio.

## SPRINT-01 — Native development preview, 2026-10-23

Research07B acceptance remains valid as permission to implement, not native
certification. Implementation was isolated in the historical sprint-01 worktree
without changing the research index; it is included in this archive. See
[docs/sprint-01.md](../sprint-01.md) for build, loading, lifecycle, input/config
and the full test record.

**SPRINT-01 BLOCKED.** Windows x64 Debug/Release compiled; native config/input/
extra tests passed. Existing ASI Loader loaded the DLL, two MinHook detours
installed, and associations were reacquired after fast travel. Implementation
preserves the first gameplay/query step and attempts A+C with preflight/XZ extra/
second-wrapper dt0, without upstream parameter multiplication. **Accepted native
extras0; animation corrections0.** A brief Shift request was observed; physical
Hold, Toggle, speed and coupling were unverified then. The game consumed pad
through Steam, but L3 did not reach native XInput polling: with Special K one
connected pad showed neutral L3, without it no pad was visible. Exclusive
Special K causality was not proven. Menus allowed movement; FF/FE alone could
not prove closed UI. Guards remained strict, without compensating latches.

Live work stopped on those gaps. Cleanup closed the game, reset pad, restored
Special K and removed only test ASI/INI/log from the game folder to ignored cache.
Original loader/Ultrawide/EXE/CPK/drivers unchanged. Detours/pages ended with the
process, no vptr swap. No limiter override or new fps:null claim. Debug/Release,
native tests, six research self-checks, Python, TOML, both diff checks and EXE/
loader hashes passed. Signed commit failed1Password; files/staging preserved
without an unsigned commit or signing-configuration change.

## SPRINT-01B — First native activation attempt, 2026-10-26

**BLOCKED — zero accepted native extras.** The final Release session was at
Bastione Oltrum: Cordia, Kirito49. Hooks were installed and invoked:2,038,897
physical entries,53,611 matching player-KCC calls (counts are not frames).
Physical Left Shift Hold requested/released independently of controller polling.
During controlled movement, identity/selector passed2,383 calls, motion flags479
calls; **all479 then failed the unchanged exact-parameter guard**. Observed
3E2F28C8=0.17105400562286377 differs from verified3E2BB98D/3E2D712B. A read-only
vanilla sample confirmed the new bits; cause UNKNOWN, without level/equipment/
buff attribution. Clip, preflight and second wrapper were not reached: this is
not collision rejection or evidence of failed A+C physical behavior.

Native counters now provide bounded snapshots/reason categories. The conservative
UI guard uses reacquired AEA4A0→game+38 bridge→field/character, vtables82C268/
82C438, embedded character=field+5C8. Main menu/inventory/skill tree showed
character state5; gameplay state0, menu pointer null, field state5. Unknown states
stay vanilla. Live inhibition of otherwise accepted extras remains unverified
because the parameter guard blocks first. L3/Steam Input mapping and disconnect/
reconnect are unresolved. Debug-only opt-in request bypass retains all guards;
two Debug launches ended during hook preparation, cause UNKNOWN, no accepted
bypass result. Standalone MinHook host tests pass both configurations; working
Release hook installation does not explain the Debug failure.

Both builds, assertion tests and static checks pass; no claim of accepted native
speed/animation, production lifecycle, collision/FPS or L3 integration. The
historical integration outlier remains UNKNOWN. Final cleanup closed the game,
neutralized/disconnected pad, removed test plugin/config/log and kept Special K
state and EXE/loader hashes unchanged. No Audio or other feature was started.

## Archival handoff — 2026-11-02

Work ended at the author's request after finishing the game. Research readiness
and native blockage are preserved separately; the archive is for continuation,
not a supported mod. The most concrete next native blocker is the unverified
new run parameter, followed by the documented L3/UI/Debug/lifecycle gaps. No
gates were relaxed for the archive, no new live test was performed and no
historical UNKNOWN was reclassified.
