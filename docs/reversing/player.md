# Player and movement

This English archival edition preserves the initial player/controller findings
and manual captures. It is historical evidence, not the final readiness decision.
Later virtual-pad, collision and lifecycle results are in movement-report.md;
the unfinished native implementation is in ../sprint-01.md. The project is
discontinued. Older statements that no hook or commit existed describe their
checkpoint, not the final repository.

Build SHA-256 `1923f0d8…9e43`, base `0x140000000`, stripped relocations. Evidence
is VANILLA STATIC unless otherwise labeled.

## October 9 collision checkpoint, superseded later

CONFIRMED static/runtime: player KCC vtable 879BD0, update+08 58D340,
preStep+38 72A160, playerStep+40 729EF0, callback+60 5875A0. Forward 72A9D0
calls projection 72B3C0 at 72ACC8, then callback return 72ADDB. For a unit
normal and factor 1, projection is v-dot(v,n)*n; target-Y store 72B5EA and ghost
publication 72A139. Synchronized Anticamera traces show negative requested Y
becoming positive actual ghost delta. Large-ascent traces did not move position
in the preStep recovery/contact callback. Movement-only 1.15 reached Y=14.218;
post-contact fallback failed. This checkpoint was NOT READY; later A+C work
supersedes that architecture and decision.

## MOVEMENT-01, initial runtime capture

The complete EXE hash was rechecked. Steam launch followed mods.ps1 off and
SKIF stopping both global Special K services. D3D11/DXGI modules came from
System32; no Special K/ReShade/ASI module was detected. Inspection used only
OpenProcess(0x410)/ReadProcessMemory, without debugger attach, breakpoints,
process writes or permanent EXE patches. An existing field save was loaded,
Kirito level 18, with three partners. Town/combat were not tested.

### Player/controller relationship

CONFIRMED VANILLA RUNTIME, PID 37196. All heap VAs below are session-only.

| Object | Session VA/value | Evidence |
|---|---|---|
| CChrPc | 21390890 | vptr 14080AE08; position follows requested physical movement |
| Physics ID | 10 | int32 at CChrPc+9FCC; -1 at title |
| Physics record | 20CB9D50 | ID in first dword, member of manager array |
| Phyre wrapper | 20CB9D60 | Record+10 |
| Player KCC | 80DF3CF0 | wrapper+148, vptr 140879BD0 |
| Backlink | 20CB9D60 | KCC+F0 equals wrapper |

Reacquire these associations after launch/load; a matching vptr alone does not
establish an active object. Static lookup 6CBEB0 reads g=[image+B148B8],
manager=[g], entries=[manager+18], count=int32[manager+134]. Each non-null
record begins with an ID. The getter returns the array slot, not the record;
dereference the slot before using record+10.

### Verified static submission chain

```text
CChrPc vtable+180 = 1EA4E0
  +548 -> 1E4BC0 -> current +9DE0
  +550 -> 1E4B40 -> requested +9E10
  1EAE27 -> 320310(physics ID, 60.0, current, requested, extra scalar)
    32037D -> 6CBEB0 -> matching physics record
    3203C8..3203CC: requested-current
    3204F4: record+104 = scalar argument = wrapper+F4
    320500: record+50 = displacement = wrapper+40, branch may adjust it
6CC090 -> 6CC13C -> 58CF40(wrapper, scalar, optional transform)
  58D2A2..58D2D2: KCC+100 = transformed displacement * wrapper+F4
  58D2E2..58D314: argument = (KCC+100).xyz * scalar
  58D31C: virtual+18 -> 72A5F0 setWalkDirection
  expected static return: image+58D31F
```

Instructions/slots/offsets are CONFIRMED; their role in observed locomotion was
initially HIGH CONFIDENCE. No entry registers/thread/stack were captured in that
first read-only session. A static expected return is not runtime stack evidence.

1F5240 copies +9DF0 to +9E10 and invokes +178/+180. 21A580 tail-jumps to
1EA4E0. 1EAE70 copies current +9DE0 to +9DF0 at 1EAF33, then calls producer
1F69B0 at 1EAF59. The producer normalizes target+9E20 minus current and adds
the integrated movement vector at 1F6EBD..1F6EC4. Other position writers include
21AF90, 235680, 219090 and 22B560.

Correction: CChrPc vtable+28 is 1E4EB0, dispatching to +308, whose player
implementation returns a constant from 904F9C. Creation routine 1EF070 is at
byte offset +140. Do not confuse byte offsets with slot indexes.

### Physical keyboard movement capture

Command: movement_probe.py 37196 0x21390890 60 physical_forward_idle.

- 5,745 non-atomic samples in 60.005 s; requested polling interval 10 ms.
- 228 nonzero samples at 35.885..38.258 s, 5,517 zero samples.
- wrapper+F4=60.0 in moving samples and 0.0 otherwise.
- Maximum KCC+50 XYZ magnitude 0.084164735 units per call.
- Start (3.926004,-0.055167,163.291428), end (-9.570621,-0.213579,155.499985).
- ID/wrapper/KCC/backlink unchanged. A later 96-sample idle check had zero
  displacement and scalar.

CONFIRMED: the identified KCC follows the player and returns to zero at rest.
The user identified this input as keyboard, not stick. Earlier Computer Use
Return/Space/W pulses produced no measurable movement; mouse reached title/load.
Captures that started after movement are idle baselines only.

### Initial speed/timing analysis

The initial interpretation of +9F24 as a movement parameter was PROBABLE,
not a proven base/max-speed name. Getter 1E4EE0 and setter 1E9980, virtual+3E8,
store RDX vector at +9E20, XMM2 at +9F24 and XMM3 at +9F2C. Alternate setter
1E9A90 is at +3F0. CChrPartner wrapper 231BB0 at +3E8 tail-jumps to the setter;
it is not a CChrPc slot beyond that vtable's first non-code entry at +990.
1F69B0 and other routines modify the parameter; 1E2640 multiplies it by
274220()+E0.

CONFIRMED static: 208FD0 starts from +9F20, conditionally applies +9F88 and
274220 table factors using virtual+648 and F8A6/F8AD, then 1BAF30 and a limit.
205BC0 stores +9F24 at 206107/2064D9/20652D and passes it with target to
virtual+3E8 at 206369. 274220 returns AEAB70. Initialization 1FE6D0,
1FE9FB..1FEA03, copies table+28 to +9F20. Runtime table values were +28=.043,
+30=3.9, +34=3.9, +38=1.38. Their relation to .043/.1677 was HIGH CONFIDENCE.
Initial combat/gait meanings of the flags were deliberately not assumed.

At 1F6ADF, producer 1F69B0 calls 69B4C0 and multiplies its return by +9FE8
at 1F6AE7. Parameter +9F24 is integrated with +9F2C and this step before scaling
the normalized direction. Getter 69B4C0 returns A63240, or A63248*60 if
C82FAC==1. Initial idle readings were approximately .529896,1.0,0 respectively,
with +9FE8=1.0.

Writer 69B430 is called at 696143 after app vfunc+D8 and cvtsd2ss. It stores
input A63238, reciprocal A6323C, fallback 60.0 for zero, and clamps input*60
between C82FA8 and A63244 into A63240. Observed input .0096343, reciprocal
103.7958, min 0, max 60, step .578058. Seconds input / 60-Hz frame units was
HIGH CONFIDENCE; do not multiply by seconds dt again.

1EAE11 reads 60.0 from A554E4 for 320310. The downstream wrapper scalar is
1/60 from 81FD40, read by 6CBD80 before 6CC090 at 6CBDA0. Earlier 820D40 was
an incorrect address. Later traces confirmed 58D31F and wrapper return 6CC141;
see the movement report. Non-atomic vector ratios alone cannot replace that trace.

## MOVEMENT-02, initial valid manual analog captures

After a further Steam Play restart the user confirmed a working controller.
Earlier non-responsive captures are excluded. New PID 62148, CChrPc 21458890,
physics ID 10, wrapper 20D81D60, KCC 80DF3CF0; vptr/backlink checked. Requested
percentages were manually approximated and are not measured internal axes.

| Requested stick | User-observed gait | Moving / total samples | Median KCC XYZ | Median KCC XZ | Median +9F24 |
|---|---|---|---|---|---|
| About 25% | Walk | 294 / 5742 | .02150515 | .02148751 | .04300000 |
| About 50% | Unclear | 929 / 5740 | .02199477 | .02197591 | .04300000 |
| About 75% | Run | 618 / 5746 | .02482157 | .02446686 | .04300000 |
| 100% | Run | 345 / 5728 | .08078582 | .08061422 | .16770001 |

25%: 60.0074 s, moving at 30.3916..34.7757 s. Start
(36.688747,.425074,178.599976), end (30.100225,.398114,174.825241).
Wrapper scalar 60.0 in 294 moving samples, zero otherwise; median
walk/velocity ratio .01666666719. Values/association are CONFIRMED runtime;
gait is USER OBSERVATION. Vector medians are not speed in units/second.

50%: 60.0010 s, moving 34.9278..45.4557 s, longer than the requested 3 s.
End (-11.016597,-.119314,184.975510). Same .043 median suggests a walk plateau,
PROBABLE, but actual input/stability remained UNKNOWN. Maximum XYZ .25625445;
walk/velocity range .01610..01988 is affected by non-atomic reads. Do not divide
the entire displacement by 3 s to infer speed.

75%: 60.0048 s, moving 49.6358..56.0976 s, ending
(13.345637,-.213579,178.954956). User-observed run with .043 median could be a
transition/unstable input; it did not establish a stable run-speed threshold.

100%: 60.0027 s, moving 19.6783..25.2399 s, ending
(40.724037,.156936,185.247192). Median parameter .16770001 is about 3.9× .043;
median XZ vector about 3.75× the 25% sample. Median walk/velocity .01666666807.
Distinct low/full-deflection parameters are CONFIRMED; a discrete gait choice
was PROBABLE. Full curve, deadzone and animation coupling were initially UNKNOWN.

## Historical Sprint candidates and readiness

The initial preferred research candidate was speed getter 208FD0, or its
player-specific consumption in 205BC0 before +9F24. It required filtering the
active CChrPc/KCC, preserving timing and passing requested position through
Bullet. A shared Bullet argument multiplier was only a diagnostic alternative;
existing locomotion-mode selection remained unverified. Equipment-load factors
were rejected as a Sprint implementation. No option was then certified
animation-safe, collision-safe or combat-safe. Later collision work explicitly
rejected the simple upstream multiplier; the final diagnostic candidate is A+C.

At this initial checkpoint Sprint was NOT READY: caller stack/thread, consumed
axes, walk/run threshold, F8A6/F8AD behavior, FPS timing and town/combat/animation
relationships still required tests. A 60-second follow-up with zero moving
samples did not validate moving flags. Later reports resolve some, not all,
of these questions. Audio, INPUT-01 and STATE-01 were not started as full phases.

Initial validation included Python syntax, TOML parse, runtime_read self-check,
runtime smoke and uniqueness of new build-local signatures. No commit was created
at that checkpoint; no EXE/CPK/save file was changed by a writing tool.

## Static Block 3 inventory

| Item | Location | Evidence / limits |
|---|---|---|
| DirectInput initialization | 64F8A0, pointer C59F18 | CONFIRMED static |
| Keyboard | Create 64F760, vtable 8AD1C0, poll 657840 | CONFIRMED static |
| Mouse | Create 64F7F0, vtable 8AD188, poll 657A21 | CONFIRMED static |
| Controller | Steam candidate 683E40/684110, no generic DI/XInput | CONFIRMED path, actual sample-path use PROBABLE |
| Input latches | 683140/687330/67EA70/68FBE0 inside 696020 | CONFIRMED static |
| Action mapping | Physical input to logical PS-style CSysPad | PROBABLE layout, exact structure UNKNOWN |
| Player | CChrPc vtable 80AE08 and runtime association above | CONFIRMED session; global-player source initially UNKNOWN |
| Position | KCC ghost position and CChrPc fields | Initially UNKNOWN offsets; later report confirms ghost+40 |
| Movement update | 1EA4E0 → 320310 → wrapper → 58CF40 → 72A5F0 | HIGH CONFIDENCE initially; runtime stack later refined |
| Bullet input | RDX vec4 → KCC+50 | HIGH CONFIDENCE Bullet side |
| Base/max speed | Initial semantic gap | Later producer/getter findings above |
| Equipment multiplier | move_speed_param.dat → stats+28 at 271436 | HIGH existence, effect initially PROBABLE |
| Delta time | App vfunc+D8, base app+E8, interval +E4 in timed-velocity mode | Initially PROBABLE |
| Combat / controllable state | CChrStatusBattle, CFighterStatusBattle, CUiModeField/Town RTTI | Full classifiers UNKNOWN |
| Generic Phyre animation gait | Metadata exists, actual player use unproven | UNKNOWN |
| Bullet integration | CChrPc creation +140 through Phyre wrapper | HIGH CONFIDENCE |

## Bullet character controller

Creation: CChrPc vtable+140, 1EF070 → 31FB90 → 6CAEB0 → 57F250 → 580080 →
5736C0, PPhysics::PInternal::PModifiedBulletKinematicCharacterController,
vtable 879BD0. Base btKinematicCharacterController has vtable 8C5550 and ctor
729B20. PPhysicsCharacterControllerComponent vfunc1, 7AAA60, and
PUtilityCharacter also reach 57F250.

| Vtable byte offset | Function | Observed behavior |
|---|---|---|
| +08 | 58D340 | Phyre updateAction(world,dt) override |
| +18 | 72A5F0 | setWalkDirection, writes +50 direction, +60 normalized direction, E3=1 |
| +20 | 72A5A0 | setVelocityForTimeInterval, same vectors, E3=0, interval +E4 |
| +28..58 | 72A4B0..729EC0 | Reset/warp/preStep/playerStep/canJump/jump/onGround sequence initially inferred from Bullet 2.8x |

Initial direct-call scanning found no direct call to the two setters because
submission is virtual at 58D31C. Preserving KCC submission preserves its sweep
pipeline, but that fact alone does not prove accelerated terrain behavior safe.
Direct position writes bypass the pipeline and were excluded.

## Existing equipment-load speed modifier

System filename table A55160 has 80 entries. Index 2C is move_speed_param.dat.
Loader 1D3768 combines a %s%s path and reads through filesystem C72D80;
buffers AEA4C0[index] give AEA620 and sizes AEA720[index] give AEA7D0.
GetSysData is 1D2FC0 and size getter 1D3010.

26F840 sums values from ten equipment slots through 36E0E0, scaling weapons
of types 1..16 or 23 by param[0]. At 271436, a chunk of derived-stat routine
270E00, six thresholds at +04..18 select a factor at +1C+i*4 into stats+28.
The same block writes stats+20/+24 total weight/+2C. This is an equipment-load
speed band, not base speed. Runtime readers were initially UNKNOWN. Changing
this visible/stat-semantic value was not recommended for Sprint.

## Locomotion-state RTTI, not demonstrated behavior

Player classes: CChrStatusMove 80A848, CPcStatusMain 825900, CChrStatusJump,
CChrStatusSquat, CPcStatusSquat, CChrStatusSit/Hug/Battle and CChrRtMove 815BB8.
NPC classes include CNpcStatusMove/Chase/Step/Avoid/Navi and
CChrUnitRunner/Chaser. RTTI alone did not establish separate player walk/run modes.

## Original proposed runtime tests

These are historical proposals; later read-only/temporary diagnostics supplied
the actual evidence. They do not authorize anti-debug bypasses. The proposed
setup was x64dbg after a vanilla Steam launch; record a Steam CEG/attach failure
rather than attempting to bypass it.

MOVEMENT-01 proposed observing 14072A5F0/14072A5A0 while idle/moving, recording
KCC RCX, return [RSP], vector [RDX], optional XMM2 interval and a four-level stack.
Shared NPC/player callers would require the resolved player-KCC filter.

MOVEMENT-02 proposed player-filtered two-second captures for partial/full stick,
keyboard, town/field and drawn weapons/combat, logging vec4 and previous +E4.
Constant, discrete and dt-proportional magnitudes would distinguish fixed speed,
gait bands and per-frame displacement. Actual manual captures above had important
timing/input limitations and must not be treated as those idealized tests.

STATE-01 proposed scanning changing byte values across field/combat/dialogue,
then identifying writers after narrowing below 200 candidates. It was not
completed; no production combat/control-state classifier follows from it.
