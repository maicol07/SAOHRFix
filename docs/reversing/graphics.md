# Graphics, D3D11 / DXGI / render loop

Build SHA-256 `1923f0d8…9e43`, see build.md. All addresses are RVAs relative to
ImageBase `0x140000000`. Findings are static VANILLA analysis, independent of
installed mods. Function boundaries come from .pdata, using half-open ranges;
leaf functions have no .pdata entry. Tools: xref.py, vcall_scan.py and sig.py.
Patterns are in research/signatures.toml; data addresses in addresses.toml.

## Block 2 summary

| Item | RVA / method | Confidence |
|---|---|---|
| Initialization | PApplication vfunc[1] 6550A0 → wrapper 4F7C80 → D3D11 init 4F7D40 | CONFIRMED |
| DXGI factory | 4F5D90, CreateDXGIFactory thunk 6EC7C8, display-mode enumeration only, factory released | CONFIRMED |
| Adapter selection | pAdapter=NULL, default adapter; EnumAdapters(0)/EnumOutputs(0) only select refresh rate | CONFIRMED |
| Device creation | 4F7FA3 inside 4F7D40, D3D11CreateDeviceAndSwapChain thunk 6EC7C2 | CONFIRMED |
| Device storage | Static renderer BAD540+A8 = BAD5E8 | CONFIRMED |
| Immediate context | BAD540+B0 = BAD5F0 | CONFIRMED |
| Swapchain storage | BAD540+B8 = BAD5F8, accessed relative to this | HIGH CONFIDENCE |
| Render loop | PhyreEngineRenderThread entry 526D10 → 53F740 → command execution 534B90 → dispatcher 531570 | CONFIRMED |
| Present | Dispatcher call 5316EA → 4F5F10 → swapchain vtable+40 at 4F5F3C | CONFIRMED |
| ResizeBuffers | WM_SIZE → app+D8 dirty → main loop 652B3F → vfunc+78 656DF0 → renderer 4FAED0 → vtable+68 call 4FAFA9 | CONFIRMED |
| HWND | C59F08, stored at 6520AD after CreateWindowExA | CONFIRMED |
| WndProc | 650440, PhyreFrameworkClass; lpfnWndProc assigned at 651EB0 | CONFIRMED |
| Render thread | Dedicated, created by 531F50, entry 526D10 | CONFIRMED |

## Reconstructed pipeline

PApplication vfunc[1] 6550A0, base vtable 8AD878, reaches wrapper 4F7C80
directly or through 654870. The wrapper reads GetClientRect and invokes
4F7D40(renderer,w,h,msaa,fullscreen?,vsync,hwnd). Argument 5 and 6 are bytes;
argument 7 is HWND. Initialization proceeds as follows:

1. Temporary D3D11CreateDevice(NULL,HW,...) probes feature level; below A000,
   FL 10_0, initialization fails.
2. When MSAA>0, another temporary device and 4F6A90 check R8G8B8A8 sample count,
   then release the device.
3. Fill DXGI_SWAP_CHAIN_DESC at renderer+C0.
4. GetSystemMetrics SM_CXSCREEN/SM_CYSCREEN and 4F5D90 select native-mode refresh.
5. D3D11CreateDeviceAndSwapChain writes renderer+A8/B0/B8.
6. Query ID3D11Debug / ID3D11InfoQueue. Release builds set no debug flag, so these
   queries may fail.
7. Swapchain GetBuffer(0,ID3D11Texture2D) writes +148; GetDesc writes +180.
8. Create RT/depth, system shaders through 4F7210/4F74D0, and states.
9. For FL>=11_0, create a DRAWINDIRECT_ARGS buffer, MiscFlags 10, at +638.
10. Bind one backbuffer RTV and depth DSV through OMSetRenderTargets.

The main thread runs PeekMessage, app animate/update and command recording.
Render loop 53F740 consumes a 16-slot ring, each slot 28 bytes, at +40. It waits
on slot semaphores, then executes through 534B90/531570. Present reads timer
544910 before and after 4F5F10, updates double BBA9C8, and releases semaphore
+2D0 to signal frame completion to the main thread.

### Device/swapchain creation arguments, CONFIRMED at 4F7F53–4F7FA3

| Argument | Value |
|---|---|
| pAdapter / Software | NULL / NULL |
| DriverType | HARDWARE 1 with HWND, otherwise WARP 5 |
| Flags | 0; no DEBUG, BGRA_SUPPORT or SINGLETHREADED flag |
| pFeatureLevels | B000/A100/A000, meaning 11_0/10_1/10_0 |
| FeatureLevels / SDKVersion | 3 / 7 |
| Output swapchain/device/context | renderer+B8/A8/B0 |
| Resulting feature level | Local value copied to +108; checked at 4F82ED for >=B000 |

The highest requested level is 11_0, not 11_1. The actual returned level is a
runtime result, expected to be 11_0 on modern hardware.

### DXGI_SWAP_CHAIN_DESC at renderer+C0, x64, 48 bytes

All listed writes are CONFIRMED.

| Offset | Field | Written value |
|---|---|---|
| +00 / +04 | Width / Height | Client rectangle dimensions |
| +08 / +0C | Refresh numerator / denominator | Initially 60/1, overwritten by 4F5D90 |
| +10 | Format | 1C, R8G8B8A8_UNORM, not SRGB |
| +14 / +18 | ScanlineOrdering / Scaling | 0/0, UNSPECIFIED |
| +1C | SampleDesc.Count | MSAA clamped to 1..16 and validated by 4F6A90 |
| +20 | SampleDesc.Quality | 0 |
| +24 | BufferUsage | 20, RENDER_TARGET_OUTPUT |
| +28 | BufferCount | 1 |
| +30 | OutputWindow | HWND |
| +38 | Windowed | !params.fullscreen |
| +3C | SwapEffect | 0, DISCARD, legacy blt model |
| +40 | Flags | 2, ALLOW_MODE_SWITCH |

This is a one-buffer DISCARD blt swapchain, not flip model, with no requested
tearing support. A future flip-model change would need creation interception.
UNORM storage and DXGI 1.0 are consistent with SDR output; the modded log's
sRGB G2.2 BT.709 SDR observation agrees with that initialization. The inference
that the game writes gamma-encoded values is not a new runtime color capture.
Refresh selection chooses the last EnumOutputs(0) R8G8B8A8 mode whose dimensions
match the desktop, using DXGI_ENUM_MODES_INTERLACED; relevant to exclusive fullscreen.

### Present, CONFIRMED

4F5F10 is 39 bytes and has one observed caller, 5316EA. It returns false for
a null renderer+B8 swapchain; otherwise calls:

```text
Present(SyncInterval = renderer[+1740] != 0 ? 1 : 0, Flags = 0)
return SUCCEEDED(hr)
```

VSync is a runtime byte written at 4F82B3 from params+D, argument 6. Interval
is only 0 or 1 and Flags is always 0, never DXGI_PRESENT_ALLOW_TEARING. Around
Present, only timer 544910, based on QPC/timeGetTime, and double BBA9C8 updates
were identified. Visible pacing involves VSync and the render-thread semaphore;
a separate main-thread limiter was UNKNOWN at this stage.

### ResizeBuffers, CONFIRMED

1. Non-minimized WM_SIZE reads GetClientRect and calls app vfunc+28, leaf
   6556C0, storing w/h at +DC0/DC4 and setting +D8 dirty. Log: WM_SIZE %4dx%4d.
2. Main loop at 652B16 checks dirty and focus transitions, flushes/waits through
   vfunc+10, 53F2F0, then calls app vfunc+78, derived 696240 → base 656DF0.
   Failure logs App failed during resize.
3. 656DF0 locks renderer through 4E7340, calls 4FAED0 and rescales viewports.
4. 4FAED0 unbinds OM targets, releases RT/depth, then at 4FAFA9 calls
   ResizeBuffers(desc.BufferCount at +E8,w,h,desc.Format at +D0,desc.Flags at +100).
   The five arguments after this establish the method identity, not just slot+68.
5. GetBuffer(0), slot+48, and texture GetDesc, slot+50, precede recreated depth/RT,
   updated descriptor dimensions and OMSetRenderTargets.

Resize does not recreate the device. The render thread is synchronized/stopped
while main-thread resize work runs.

### Fullscreen, focus and device reset

| Concern | Evidence | Confidence |
|---|---|---|
| SetFullscreenState(FALSE,NULL) | Shutdown 4FEAB0, call 4FEBEB, before Release | CONFIRMED |
| GetFullscreenState | Game-app vfunc 697C30, vtable 8B53E0[51], writes app+12AC | CONFIRMED |
| Fullscreen toggle | No TRUE call found; 4F5D90 does not call MakeWindowAssociation, other factory users unexamined. Default DXGI Alt+Enter is likely, but WndProc handles WM_SYSKEYDOWN | PROBABLE |
| WM_ACTIVATE | 654D20 → app vfunc+30 → +DA active, +D9 changed → main-loop vfunc+88 | CONFIRMED |
| SIZE_MINIMIZED | C59F05=1 and app vfunc+30(0) | CONFIRMED |
| Device removed/lost handling | No explicit recovery found; failed Present only returns false | PROBABLE absence, not exhaustive proof |

## Window and WndProc

651E80 registers PhyreFrameworkClass with WndProc 650440, adjusts the rectangle
and calls CreateWindowExA, unless params+30 already supplies a host HWND. It
stores C59F08, sets GWLP_USERDATA to app, and registers device notifications.
Global app pointer C59F38 is written by ctor 64A270, whose default dimensions
are 1280×720.

WndProc 650440 and chained chunks 650491/6504C4/650512 retrieve app through
GWLP_USERDATA. They handle WM_CREATE 1, WM_DESTROY 2, WM_SIZE 5, WM_ACTIVATE 6,
WM_CLOSE 10, WM_ERASEBKGND 14, WM_GETMINMAXINFO 24, WM_SYSKEYDOWN 104,
WM_DEVICECHANGE 219 and registered PHYREMSG_HOSTHWND; other messages reach
DefWindowProcA. Gameplay keyboard/mouse input is polled, not handled here.

A future overlay would need both WndProc event handling and suppression of game
polling. A candidate WndProc interception is SetWindowLongPtrA on the actual
HWND after creation, without patching game code. No overlay was implemented.

## Static renderer object BAD540

Lazy singleton accessor 4F6E30 uses guard BAECA0 and lock 4E7340. Only observed
offsets are named below.

| Offset | Observed use | Confidence |
|---|---|---|
| +94..A0 | Four dwords copied from app+E08 before initialization; possible dimensions | UNKNOWN meaning |
| +A8 / +B0 / +B8 | D3D11 device / immediate context / DXGI swapchain | CONFIRMED |
| +C0 | DXGI_SWAP_CHAIN_DESC, 48 bytes | CONFIRMED |
| +108 | Returned feature level | CONFIRMED |
| +110 | Pointer to BF7CB8, possibly an RT format/descriptor | UNKNOWN |
| +138 / +13C | Backbuffer width/height from GetDesc | HIGH CONFIDENCE |
| +148 | Backbuffer ID3D11Texture2D array, count at +140 | HIGH CONFIDENCE |
| +180 | Backbuffer D3D11_TEXTURE2D_DESC | CONFIRMED |
| +250 | Backbuffer RT object, RTV through 4F6EF0 | HIGH CONFIDENCE |
| +2F8 | Depth object, DSV through 4F6A50 | HIGH CONFIDENCE |
| +638 | DRAWINDIRECT_ARGS buffer for FL>=11_0 | CONFIRMED |
| +1740 | VSync interval byte | CONFIRMED |

## Render thread and historical hook recommendation

531F50 creates semaphores +2C0, count 16, and +2D0, count 1, with 16 slots.
5452B0 wraps CreateThread with a 10000-byte stack and name
PhyreEngineRenderThread, entry 526D10. Loop 53F740 names itself RenderThread;
state +28 uses 0 idle, 1 execute, 2 exit. Frame D3D11 commands pass through the
43-case, 2B, dispatcher 531570. Initialization, resize and shutdown instead run
on the main thread with rendering synchronized.

The original preferred proposal was to capture the real swapchain through the
D3D11CreateDeviceAndSwapChain IAT slot 7FEA88, or read BAD5F8 if initialization
had already occurred. Then detour the actual vtable+40 Present and +68
ResizeBuffers functions with MinHook, accounting for ReShade/Special K wrappers.
Resize interception would be required to release overlay RTVs. The build-local
4F5F10 wrapper/dispatcher case was considered useful for observation, not the
primary overlay hook, because Present is a queued render-thread command.

Present runs on the render thread; WndProc and input polling run on the main
thread. A future implementation would require safe input-state transfer and
main-thread game-input suppression. These were proposals, not validated mod
compatibility or a completed rendering feature.

Unresolved leads: extra factory callers 166540/6977C0, main-loop limiter/dt, and
the preliminary resource-creation map in rendering.md.
