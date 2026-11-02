# Reverse-engineering notebook

Historical hypotheses and open leads. Confirmed findings belong in the relevant
report; rejected ideas retain their reason. The project is discontinued. The
movement report and native Sprint handoff supersede early movement readiness
statements here. Reference build: SHA-256 `1923f0d8…9e43`.

## Block 2, findings in graphics.md

Low-impact open leads:

- Extra CreateDXGIFactory callers 166540 and 6977C0 also call
  CreateShaderResourceView. They may enumerate modes for options or thumbnails.
- WndProc handles WM_SYSKEYDOWN, 104. Whether this implements custom Alt+Enter
  remained unverified.
- Global double BBA9C8 is updated after every Present; it is a frame-time candidate.
- App animate 696020, vtable 8B53E0+50, computes a 16:9 letterbox/pillarbox
  viewport at app+11D0..11DC when app+12AA is set, comparing w/16 with h/9.
  This is a likely Ultrawide patch point. Delta time comes through vfunc D8.

REJECTED: swapchain creation through IDXGIFactory::CreateSwapChain. The observed
creation is D3D11CreateDeviceAndSwapChain at 4F7FA3; the factory enumerates modes.
REJECTED: 35F3C1 call [rax+68] as ResizeBuffers. It was a gameplay-object false positive.

## Block 3, historical static leads

MOVEMENT-01 confirmed the runtime chain CChrPc+9FCC → physics record →
wrapper+148 → KCC, with KCC+F0 backlink. Initial movement/rest capture was positive;
session addresses and results are in player.md. Static caller 58D31C and candidate
gameplay chain 1EA4E0 → 320310 were identified; initial actual stack/thread remained
UNKNOWN. CChrPc creation slot is +140, not +28.

Speed getter 208FD0 reads base +9F20 from AEAB70+28 and produces +9F24.
Early approximate stick 25/50/75/100 captures had median 0.043 at the first three
levels and 0.1677 at full deflection. The full-deflection parameter choice was
HIGH CONFIDENCE; threshold/gait questions were later resolved in the movement
report. Locomotion step 69B430 produces A63240 from clamped app dt*60;
69B4C0 returns the selected timing source. The later report supersedes these
initially open FPS, MOVEMENT-02 and Sprint decisions.

Remaining input/animation leads:

- Purpose of SetWindowsHookExA at 695990 and the second GetKeyboardState paths
  at 68EE20/6903B0.
- RegisterDeviceNotificationA at 6520FA and WM_DEVICECHANGE. The filter probably
  covers HID/interfaces, but audio-endpoint coverage was not verified.
- Phyre reflection metadata PCharacterMotionGait, m_gaits, m_speedMultiplier,
  m_speedAdjust, m_animSpeedLimit, m_motionAnimSpeedScale,
  m_animIdleSpeedThreshold, updateSpeed, getCurrentSpeed and setMaximumSpeed.
  Actual player use of these generic facilities was not demonstrated; do not
  substitute them for the verified game-specific animation chain.
- PModifiedBulletKinematicCharacterController::updateAction override 58D340.
- Game animation strings sysMotion, CChrMotion and CChrModelBaseMot.

REJECTED: an Xbox controller enumerated as generic DirectInput. Callback 64E250
accepts only DI8DEVTYPE_MOUSE 12 and DI8DEVTYPE_KEYBOARD 13.
REJECTED: active main-module ASLR. Relocations are stripped and the module loads
at 140000000.

## Audio leads, dedicated Block 4 not started

- Library-level backend: CRI ADX2, ASR renderer, NcVoice WASAPI/PCx64 1.25.00.
- CoCreateInstance probably creates IMMDeviceEnumerator inside NcVoice.
- Useful string anchors: W2014021962 at 8D0AD0, WASAPI unavailable/silent output;
  E2013042461 at 8D0B30, WASAPI finalized with active handles; E2016012822,
  ASR must be initialized for CRIATOM_SOUND_RENDERER_ASR.
- A proposed device-hot-swap investigation would locate the game's use of
  criAtom_Finalize → criAtom_Initialize/criAtomAsr_Initialize, or first inspect
  IAudioClient::Initialize and endpoint creation inside NcVoice. These are ideas,
  not implemented fixes or demonstrated safe callback paths.
- Shared-mode eRender/eConsole selection and handling of
  AUDCLNT_E_DEVICE_INVALIDATED remain unverified.

## Filesystem/loading leads, dedicated Block 5 not started

- Archive strings pkg/data.cpk at 801A80 and pkg/%s.cpk at 801A90 use language
  codes such as ita/usa/ger, consistent with the installation's pkg files.
- CriFsBinder/PCx64 1.02.70 is confirmed at 8D31E1. Anchors include
  CriFsBinder_GetWorkSizeBindCpk at 8D35E0/8D4B00, BindFiles:: at 8D36C8 and
  criFs_InitializeLibrary/criFs_FinalizeLibrary at 8D3020.
- The CRI binder is a natural VFS candidate. BindCpk and BindFiles are present.
  criFsBinder_BindDirectory has no observed string, which does not prove that
  the function is absent. Binder priority was never verified, so a safe VFS hook
  remains undetermined. CreateFileA/W and ReadFile were only coarse fallback ideas.
- Names such as custom_chr_tone.fx#CA68C990DF8603BDFDE0BB809E8C0570.phyre
  suggest MD5-like content/permutation hashes, perhaps explaining CryptoAPI use.
- %s%s.phyre at 827EA8 suggests runtime asset-name composition as another
  possible override interception point.

## Rendering/camera/timing leads

- Shader strings include /Shaders/prim_shader.fx.phyre, prim_shader_tex,
  prim_shader_zpre, prim_shader_effect and /sys/dith_mask.dds.phyre. zpre suggests
  a depth prepass and early availability of full depth, not a verified pass capture.
- Modded dlss5-feed.log observations: sRGB G2.2 BT.709 SDR swapchain,
  PhyreFrameworkClass and depth reversed=1. Vanilla reversed-Z remains unverified.
- Motion vectors have no supporting evidence. The initial working assumption
  was absence, with a future temporal upscaler requiring generation; this is
  not proof that the game has no velocity data.
- timeBeginPeriod, QPC and fibers indicate high-resolution timing. The original
  60-FPS-cap question proposed examining Present SyncInterval versus an internal
  limiter. Later movement/timing captures are documented separately.

No audio, VFS, temporal-upscaling or graphics feature implementation followed.
