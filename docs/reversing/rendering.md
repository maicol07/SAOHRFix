# Rendering — reconnaissance

Build: `sha256 1923f0d8…9e43`. Stato: solo fatti emersi dal blocco 2. Analisi dei pass → blocco 6.

## Fatti già stabiliti

| Fatto | Fonte | Stato |
|---|---|---|
| Backbuffer `R8G8B8A8_UNORM`, 1 buffer, blt model DISCARD, MSAA opzionale 1–16 | statica `0x4F7D40` (`graphics.md`) | CONFIRMED · VANILLA |
| Output SDR, nessun path HDR/colour-space | statica (format UNORM, DXGI 1.0; nessun `SetColorSpace1` nell'init) | HIGH CONFIDENCE · VANILLA |
| Feature level max 11_0 | statica | CONFIRMED · VANILLA |
| Backbuffer RT in `renderer+0x250`, depth target in `renderer+0x2F8`, bound insieme all'init | statica `0x4F8345`–`0x4F836F` | HIGH CONFIDENCE · VANILLA |
| Depth prepass (`prim_shader_zpre.fx.phyre`) | stringa | PROBABLE (esistenza del pass) |
| Depth reversed-Z | solo `dlss5-feed.log` (`depth reversed=1`) | HIGH CONFIDENCE · **MODDED** — da confermare |
| Shader precompilati (`*.fx.phyre`), nessun `d3dcompiler` | import table | CONFIRMED |

## Mappa preliminare call site D3D11 (per blocco 6)

Metodo: `call [vtbl+slot]` entro 14 istruzioni da un load del device (`+0xA8` o globale `0xBAD5E8`) o del
context (`+0xB0` o `0xBAD5F0`). **Heuristica, incompleta**: manca ogni sito dove il device arriva come argomento.

| API | Slot | Funzioni trovate (`.pdata` begin) |
|---|---|---|
| `ID3D11Device::CreateTexture2D` | `+0x28` | `0x4EFF57`, `0x5050B0`, `0x581600`, `0x5F9C80` |
| `ID3D11Device::CreateShaderResourceView` | `+0x38` | `0x166540`, `0x6977C0` |
| `ID3D11Device::CreateRenderTargetView` | `+0x48` | non trovati con questa heuristica |
| `ID3D11Device::CreateDepthStencilView` | `+0x50` | non trovati con questa heuristica |
| `ID3D11Device::CreateVertexShader` | `+0x60` | `0x4F7210`, `0x4F74D0`, `0x569000`, `0x569360`, `0x56C770`, `0x56D8CB` |
| `ID3D11Device::CreatePixelShader` | `+0x78` | `0x4F7210` |
| `ID3D11DeviceContext::OMSetRenderTargets` | `+0x108` | `0x4EDD00`, `0x4FAED0`/`0x4FAF90` (resize), `0x4FDB50`, `0x4FEAB0` (shutdown) |

Wrapper di RT/DS già visti: `0x4F6EF0` (RT object → RTV), `0x4F6A50` (DS object → DSV), `0x4FED80`
(release target), `0x53B9A0` / `0x531F40` / `0x4EDB70` (creazione target secondari all'init e al resize,
argomenti `w,h` e descrittori a `0xBF7CB8` / `0xBF8380`). Da analizzare nel blocco 6.

## Test runtime previsto (blocco 6, non ancora richiesto)

Capture RenderDoc **VANILLA** (`tools/mods.ps1 off`) per: lista RT/formati/dimensioni, ordine pass, depth
format e convenzione Z, presenza di velocity buffer, punto di separazione HUD. Procedura in blocco 6.
