# Rendering reconnaissance

Build SHA-256 `1923f0d8…9e43`. These are findings from Block 2. Dedicated render
pass analysis, originally planned as Block 6, was not completed.

## Established findings

| Finding | Source | Status |
|---|---|---|
| R8G8B8A8_UNORM backbuffer, one buffer, DISCARD blt model, optional 1–16 MSAA | Static 0x4F7D40, graphics.md | CONFIRMED, VANILLA |
| SDR output, no identified HDR/color-space path | UNORM format, DXGI 1.0, no SetColorSpace1 during initialization | HIGH CONFIDENCE, VANILLA |
| Maximum feature level 11_0 | Static | CONFIRMED, VANILLA |
| Backbuffer RT at renderer+250, depth target at +2F8, bound together during initialization | Static 4F8345–4F836F | HIGH CONFIDENCE, VANILLA |
| Depth prepass | prim_shader_zpre.fx.phyre string | PROBABLE, pass existence |
| Reversed-Z depth | dlss5-feed.log, depth reversed=1 | HIGH CONFIDENCE, MODDED observation only; vanilla unconfirmed |
| Precompiled .fx.phyre shaders, no d3dcompiler import | Import table | CONFIRMED |

## Preliminary D3D11 call-site map

The heuristic finds `call [vtbl+slot]` within 14 instructions of a device load
from +A8 or BAD5E8, or a context load from +B0 or BAD5F0. It is incomplete and
misses sites receiving the device as an argument.

| API | Slot | Functions found, .pdata starts |
|---|---|---|
| ID3D11Device::CreateTexture2D | +28 | 4EFF57, 5050B0, 581600, 5F9C80 |
| ID3D11Device::CreateShaderResourceView | +38 | 166540, 6977C0 |
| ID3D11Device::CreateRenderTargetView | +48 | Not found with this heuristic |
| ID3D11Device::CreateDepthStencilView | +50 | Not found with this heuristic |
| ID3D11Device::CreateVertexShader | +60 | 4F7210, 4F74D0, 569000, 569360, 56C770, 56D8CB |
| ID3D11Device::CreatePixelShader | +78 | 4F7210 |
| ID3D11DeviceContext::OMSetRenderTargets | +108 | 4EDD00, 4FAED0/4FAF90 resize, 4FDB50, 4FEAB0 shutdown |

Previously identified RT/DS wrappers: 4F6EF0 converts RT object to RTV; 4F6A50
converts DS object to DSV; 4FED80 releases a target. 53B9A0, 531F40 and 4EDB70
create secondary targets at initialization/resize, with w/h arguments and
descriptors at BF7CB8/BF8380. These were candidates for later analysis.

## Proposed runtime test, not performed

A vanilla RenderDoc capture, after reversible mods.ps1 off, was intended to
record render targets, formats/sizes, pass order, depth format/Z convention,
velocity buffers and the HUD separation point. It remains unperformed.
