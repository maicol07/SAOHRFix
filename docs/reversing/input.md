# Input

Build SHA-256 `1923f0d8…9e43`, RVAs relative to `0x140000000`. Unless stated
otherwise, this is VANILLA STATIC analysis. Later native limitations are in
docs/sprint-01.md; no general INPUT-01 completion is claimed.

## Initial runtime observations

MOVEMENT-01 reached loading through Computer Use mouse input. Early synthetic
keyboard pulses produced no measurable movement. The user's physical keyboard
movement was confirmed through KCC/position readings and identified by the user
as keyboard input. Initial analog captures were invalid when the controller did
not respond through Steam Input; hot plugging remained unverified.

The UI later showed Steam Input enabled, a recognized PlayStation controller,
the official AQURIA layout and left stick assigned to Move. steam_api64.dll,
steamclient64.dll and gameoverlayrenderer64.dll were loaded. Initial launch used
steam://rungameid/607890; a later restart used Steam's Play button. The user then
confirmed working controller input. This is CONFIRMED USER OBSERVATION, with
cause UNKNOWN. It does not prove that the launch protocol or hot plugging caused
the difference, or that the sample ISteamController path below was used.

The main module has stripped relocations, so this build loads at 140000000.

## Reconstructed pipeline

DirectInput8 keyboard/mouse reader threads, the Steam/gamepad reader PadRead,
and the USER32 keyboard-state path latch their protected state on the main
thread inside app animate 696020. The latch calls are keyboard 683140, mouse
687330, pad 67EA70 and GetKeyboardState 68FBE0. Gameplay update 165A10 follows
those latches. Each relevant reader/latch uses its own mutex.

The PS4/Vita-derived gameplay operates on a PlayStation-style logical CSysPad,
with Cross/Circle/Square/Triangle/StartOption/SelectShare/TouchPad names.
Keyboard input reaches this logical pad through CUiKeyConfigWin32,
CKeyConfigWin32Proc and key_config*.dat, rather than bypassing game mapping.

## DirectInput

| Item | RVA / behavior | Confidence |
|---|---|---|
| DirectInput8Create | 64F8A0, call 64F8CB, thunk 6EA76C, from app init 6550A0 | CONFIRMED |
| IDirectInput8 pointer | C59F18 | CONFIRMED |
| Enumeration | EnumDevices(DI8DEVCLASS_ALL,64E250,NULL,DIEDFL_ATTACHEDONLY) | CONFIRMED |
| Device filter | dwDevType low byte 13 keyboard → 64F760; 12 mouse → 64F7F0; all others ignored | CONFIRMED |
| Keyboard creation | CreateDevice, c_dfDIKeyboard at 8C22F8, 256 bytes, cooperative flags 6 NONEXCLUSIVE/FOREGROUND, Acquire; PInputDeviceKeyboard size 150, ctor 64A870, vtable 8AD1C0 | CONFIRMED |
| Mouse creation | c_dfDIMouse2 at 8C22D8, 20 bytes/11 objects, flags 6; PInputDeviceMouse size 200, ctor 64A910, vtable 8AD188 | CONFIRMED |
| Generic joystick/gamepad DirectInput | None, rejected by enumeration filter | CONFIRMED |
| Keyboard poll | vfunc[5] 657840, GetDeviceState(256); clears state and reacquires on DIERR_INPUTLOST; maps 96 engine codes through DIK table A625C0 into this+F0 held state, then edge helper 6577A0 | CONFIRMED poll; arrays +30/+90 pressed/released semantics PROBABLE |
| Mouse poll | 657A21, GetCursorPos/GetWindowRect/GetClientRect/GetWindowInfo/ScreenToClient; client coordinates scaled by 255 to +1F0/+1F4, +1F8; button bit7 to +1FC..1FE | CONFIRMED |
| Buffered GetDeviceData / Unacquire | Not found in the polling path | PROBABLE immediate-state-only path |

## Steam Input / ISteamController candidate path

No XInput, HID or generic joystick DirectInput path was found in the game
binary. Steamworks SteamController005 and PInputDevicePadSteamController /
CSteamControllerTest are present. Their presence is CONFIRMED; actual use of
the following sample-named code remains PROBABLE, pending INPUT-01.

683E40 obtains action sets ship_controls/menu_controls and digital actions
turn_left, turn_right, forward_thrust, backward_thrust, fire_lasers, pause_menu,
menu_up/down/left/right/select/cancel, plus analog_controls. Vtable offsets
+28/+40/+58 match SteamController005. Poll 684110, chunk 684181, activates an
action set at +30 and performs five 684540 digital reads. It logs controller
disconnection. These are Valve SpaceWar sample names; either the game reuses
them in its manifest or the sample code is unused. Static evidence does not
resolve that distinction.

67E870 creates PadRead and PadMutex, handle C69070. Main-thread latch 67EA70
calls 67D640/67E4C0. Physical stick/trigger/L3/R3 encoding and deadzones remain
UNKNOWN. Steam may transform physical buttons into actions. A future L3 bind
must identify the consumed logical state or an appropriate Steam action; raw
Windows polling does not establish what the game receives.

## Additional USER32 polling

| API | Sites | Interpretation |
|---|---|---|
| GetKeyboardState | 68EE20, call 68F3AC under mutex C6BF80, latched by 68FBE0; also 6903B0, call 6904A7 | Independent of DirectInput; key configuration/text purpose PROBABLE |
| GetKeyState | 6828F0, call 68294B | Probably toggle state such as CapsLock/NumLock |
| GetCursorPos / ScreenToClient | 657A21 | Absolute client mouse position |
| GetAsyncKeyState | Not imported by the game | CONFIRMED |
| SetWindowsHookExA | 695990, call 6959E4 | Hook type/purpose UNKNOWN |
| Raw Input | Not imported | CONFIRMED |

WndProc 650440 does not process gameplay keyboard/mouse input. See graphics.md.

## Logical mapping and threads

Phyre PInputs::PInputMap/PInputAction/PInputSource* and PInputMapper RTTI exists,
but gameplay use is UNKNOWN. Game-level classes include CSysInputDevice,
vtable 8B4D48; CSysKeyboard 8B48A8; CSysPad 8B4840; keyboard/gamepad key-config
UI and CKeyConfigWin32Proc. A physical-to-logical mapping layer exists, but its
complete layout/action count was not recovered.

Reader thread roles are HIGH CONFIDENCE from names/mutexes. Main-thread latch
locations and their ordering before gameplay are CONFIRMED. A future overlay
could intercept the four main-thread latches, preserving reader consistency
under the existing mutexes. Whether to clear or skip mapped input was not
decided or implemented. Filtering WndProc alone would not suppress gameplay.
Main-thread WndProc events and render-thread overlay drawing would require safe
state transfer, such as a queue/double buffer.

## Proposed INPUT-01, not completed

Purpose: establish whether 684110 supplies actual gamepad data. The historical
proposal was to attach x64dbg after Steam launch, observe 684181/684540 while
moving and pressing A, record a short call stack, remove breakpoints, and compare
Steam Input enabled/disabled. No invasive anti-debug bypass is authorized or
implied by this historical proposal. The game uses Steam CEG/IsDebuggerPresent;
an attach failure must be recorded rather than bypassed.

Candidate interpretations were: breakpoint hit plus no pad without Steam Input
would support the Steam path; no hit would require following another path from
67EA70. These outcomes were not collected as a completed INPUT-01.

## MOVEMENT-01/02 consumed analog input, October 1, 2026

CONFIRMED static: 205BC0 gets the axis object through 1CE560, calls 2D0290 and
2D04D0 with history 0, and retains signed16 axes in R12D/R15D. Input ring
C66D60 has 64 records of 8C bytes, with X/Y at +80/+82; history count C69060,
cursor C69068. With history active, latest slot is (cursor-1)%64; count zero
selects the base record. Axis-object+70E may invert the sign.

CONFIRMED runtime: an Xbox virtual pad through the pre-existing ViGEmBus,
connected before Steam launch, produces internal axes and movement. It does
not establish a new XInput path inside the game. Requested software percentages
are not consumed-axis percentages.

At analog branch 20646A, R12D becomes X² and R15D X²+Y². The 1E9980 setter
trace with return 1E993F and outer return 206660 captures that consumed magnitude.
This interpretation applies only to those verified callers. Ring polling,
setter events and KCC submissions differ in phase/thread and are not atomic
frame snapshots. See movement-report.md for thresholds, results and limitations.
