# Graphics — D3D11 / DXGI / render loop

Build: `sha256 1923f0d8…9e43` (vedi `build.md`). Tutte le RVA sono relative a ImageBase `0x140000000`.
Tutte le scoperte di questo documento sono **statiche → `VANILLA`** (nessuna dipendenza dalle mod installate).
Boundaries da `.pdata` (`[begin, end)`), salvo dove indicato "leaf" (nessuna entry `.pdata`).

Strumenti: `tools/xref.py` (xref/disasm), `tools/vcall_scan.py`, `tools/sig.py`. Signature in
`research/signatures.toml`, indirizzi dati in `research/addresses.toml`.

## Tabella riassuntiva (DoD blocco 2)

| Elemento | RVA / metodo | Confidence |
|---|---|---|
| Graphics initialization | `PApplication::vfunc[1]` `0x6550A0` → `0x4F7C80` (wrapper) → `0x4F7D40` (init D3D11) | CONFIRMED |
| DXGI factory creation | `0x4F5D90`: `CreateDXGIFactory` (thunk `0x6EC7C8`) — solo per enumerare display mode, factory rilasciata | CONFIRMED |
| Adapter selection | Nessuna: `pAdapter = NULL` (adapter di default). `0x4F5D90` usa `EnumAdapters(0)`/`EnumOutputs(0)` solo per il refresh rate | CONFIRMED |
| D3D11 device creation | `0x4F7D40` @ `0x4F7FA3`: `D3D11CreateDeviceAndSwapChain` (thunk `0x6EC7C2`) | CONFIRMED |
| Device pointer/storage | renderer static `0xBAD540` + `0xA8` = **`0xBAD5E8`** (referenziato anche come globale) | CONFIRMED |
| Context pointer/storage | `0xBAD540 + 0xB0` = **`0xBAD5F0`** (referenziato come globale) | CONFIRMED |
| Swapchain pointer/storage | `0xBAD540 + 0xB8` = **`0xBAD5F8`** (solo accessi `this`-relative) | HIGH CONFIDENCE |
| Render loop | Render thread `PhyreEngineRenderThread`: entry `0x526D10` → loop `0x53F740` → exec cmd buffer `0x534B90` → dispatcher `0x531570` | CONFIRMED |
| Present path | `0x531570` (case comando Present) @ `0x5316EA` → wrapper **`0x4F5F10`** → `IDXGISwapChain::Present` (vtbl `+0x40`) @ `0x4F5F3C` | CONFIRMED |
| ResizeBuffers path | WndProc `WM_SIZE` → `app+0xD8` dirty → main loop `0x652B3F` → `app::vfunc[0x78]` `0x656DF0` → renderer resize **`0x4FAED0`** → `ResizeBuffers` (vtbl `+0x68`) @ `0x4FAFA9` | CONFIRMED |
| HWND | globale **`0xC59F08`** (scritto a `0x6520AD` subito dopo `CreateWindowExA`) | CONFIRMED |
| WndProc | **`0x650440`** (class `PhyreFrameworkClass`, `lpfnWndProc` @ `0x651EB0`) | CONFIRMED |
| Render thread | Dedicato. Creato da `0x531F50` (`"PhyreEngineRenderThread"`, thread proc `0x526D10`) | CONFIRMED |

## Pipeline ricostruita

```
PApplication::vfunc[1] 0x6550A0                  (init applicazione; vtable base 0x8AD878)
  └─ 0x654870 / diretto → 0x4F7C80(renderer, params)
        GetClientRect(params->hwnd) → width/height = client rect
        └─ 0x4F7D40(renderer, w, h, msaa, fullscreen?, vsync, hwnd)   [arg5 byte, arg6 byte, arg7 HWND]
              1. D3D11CreateDevice(NULL, HW, …, NULL, 0, 7, NULL, &fl, NULL)   probe feature level
                 fallisce se fl < 0xA000 (FL 10_0)
              2. [MSAA > 0] D3D11CreateDevice temporaneo → 0x4F6A90 (check sample count R8G8B8A8) → Release
              3. riempie DXGI_SWAP_CHAIN_DESC in renderer+0xC0
              4. GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN) → 0x4F5D90 → refresh rate del display mode nativo
              5. D3D11CreateDeviceAndSwapChain(…) → renderer+0xA8/+0xB0/+0xB8
              6. QI ID3D11Debug / ID3D11InfoQueue (fallisce in release, nessun debug flag)
              7. swapchain->GetBuffer(0, ID3D11Texture2D) → renderer+0x148 ; GetDesc → +0x180
              8. crea RT/depth, shader di sistema (0x4F7210, 0x4F74D0), stati
              9. [FL ≥ 11_0] device->CreateBuffer (MiscFlags 0x10 DRAWINDIRECT_ARGS) → renderer+0x638
             10. context->OMSetRenderTargets(1, backbuffer RTV, depth DSV)

main thread: PeekMessage loop → app update ("animate") → registra command buffer
render thread 0x53F740: ring 16 slot (0x28 B) @ +0x40, wait semaforo slot → 0x534B90 → 0x531570
  case Present: t=0x544910(); 0x4F5F10(renderer) ; t=0x544910(); globale double 0xBBA9C8 aggiornato
                → release semaforo +0x2D0 (frame done → main thread)
```

### Parametri `D3D11CreateDeviceAndSwapChain` (CONFIRMED, `0x4F7F53`–`0x4F7FA3`)

| Parametro | Valore |
|---|---|
| `pAdapter` | `NULL` |
| `DriverType` | `D3D_DRIVER_TYPE_HARDWARE` (1) se HWND ≠ NULL, altrimenti `WARP` (5) |
| `Software` | `NULL` |
| `Flags` | `0` (niente `DEBUG`, niente `BGRA_SUPPORT`, niente `SINGLETHREADED`) |
| `pFeatureLevels` | `{0xB000, 0xA100, 0xA000}` = `11_0, 10_1, 10_0` |
| `FeatureLevels` | `3` |
| `SDKVersion` | `7` |
| `ppSwapChain` / `ppDevice` / `ppImmediateContext` | `renderer+0xB8` / `+0xA8` / `+0xB0` |
| `pFeatureLevel` | locale → copiato in `renderer+0x108` (riletto a `0x4F82ED`: path extra se ≥ `0xB000`) |

Feature level massimo richiesto: **11_0**. Nessun 11_1. Feature level ottenuto: runtime (su HW moderno: 11_0).

### `DXGI_SWAP_CHAIN_DESC` @ `renderer+0xC0` (x64, 0x48 byte)

| Offset | Campo | Valore scritto | Confidence |
|---|---|---|---|
| +0x00 | `BufferDesc.Width` | client width | CONFIRMED |
| +0x04 | `BufferDesc.Height` | client height | CONFIRMED |
| +0x08 | `RefreshRate.Numerator` | 60, poi sovrascritto da `0x4F5D90` | CONFIRMED |
| +0x0C | `RefreshRate.Denominator` | 1, idem | CONFIRMED |
| +0x10 | `BufferDesc.Format` | `0x1C` = `DXGI_FORMAT_R8G8B8A8_UNORM` (**non** `_SRGB`) | CONFIRMED |
| +0x14 / +0x18 | `ScanlineOrdering` / `Scaling` | 0 / 0 (UNSPECIFIED) | CONFIRMED |
| +0x1C | `SampleDesc.Count` | MSAA clamp `[1,16]`, validato da `0x4F6A90` | CONFIRMED |
| +0x20 | `SampleDesc.Quality` | 0 | CONFIRMED |
| +0x24 | `BufferUsage` | `0x20` = `DXGI_USAGE_RENDER_TARGET_OUTPUT` | CONFIRMED |
| +0x28 | `BufferCount` | **1** | CONFIRMED |
| +0x30 | `OutputWindow` | HWND | CONFIRMED |
| +0x38 | `Windowed` | `!params.fullscreen` | CONFIRMED |
| +0x3C | `SwapEffect` | **0 = `DXGI_SWAP_EFFECT_DISCARD`** (blt model legacy) | CONFIRMED |
| +0x40 | `Flags` | `2` = `DXGI_SWAP_CHAIN_FLAG_ALLOW_MODE_SWITCH` | CONFIRMED |

Conseguenze:
- Blt model + 1 buffer + DISCARD: niente flip model, niente tearing, niente VRR "vero" in windowed.
  Upgrade a flip model possibile in futuro intercettando la creazione (vedi hook strategy).
- Backbuffer UNORM lineare: il gioco scrive valori già gamma-encoded. Nessun HDR.
  → **conferma statica** di "sRGB G2.2 BT.709 SDR" riportato da `dlss5-feed.log` (quel dato ora è VANILLA-coerente).
- Refresh rate: ultimo display mode di `EnumOutputs(0)` con `Width==SM_CXSCREEN && Height==SM_CYSCREEN`,
  formato R8G8B8A8, `DXGI_ENUM_MODES_INTERLACED`. Rilevante solo in fullscreen esclusivo.

### Present (CONFIRMED)

`0x4F5F10` — 0x39 byte, unico caller `0x5316EA`:
```
rcx = renderer->swapchain (+0xB8); if NULL return false
Present(SyncInterval = (renderer+0x1740 != 0) ? 1 : 0, Flags = 0)
return SUCCEEDED(hr)
```
- Due argomenti oltre al `this` → coerente con `Present(UINT SyncInterval, UINT Flags)`.
- **VSync = booleano runtime** in `renderer+0x1740`, impostato da `0x4F82B3` con `params+0xD`
  (6° argomento dell'init). SyncInterval è solo 0 o 1. `Flags` sempre 0 → mai `DXGI_PRESENT_ALLOW_TEARING`.
- Nessun limiter visibile attorno a Present: solo due letture del timer `0x544910` (QPC+`timeGetTime`)
  e aggiornamento del globale double `0xBBA9C8`. Il pacing apparente = VSync + semaforo render thread.
  Limiter nel main thread: **UNKNOWN** → blocco 7 (`timing.md`).

### ResizeBuffers (CONFIRMED)

Flusso:
1. WndProc `WM_SIZE` (non minimized) → `GetClientRect` → `app->vfunc[0x28]` = `0x6556C0` (leaf):
   salva `w,h` in `app+0xDC0/0xDC4`, `app+0xD8 = 1` (dirty). Log: `"WM_SIZE %4dx%4d\n"`.
2. Main loop (`0x652B16`): se dirty e non in cambio focus → flush/attesa render thread (`vfunc[0x10]`, `0x53F2F0`)
   → `app->vfunc[0x78]` (derived `0x696240` → base `0x656DF0`). Log errore: `"App failed during resize…"`.
3. `0x656DF0`: lock renderer (`0x4E7340`), `0x4FAED0(renderer, w, h)`, poi riscala i viewport.
4. `0x4FAED0`: `OMSetRenderTargets(0,NULL,NULL)`, release RT/depth, poi @ `0x4FAFA9`:
   `ResizeBuffers(desc.BufferCount[+0xE8], w, h, desc.Format[+0xD0], desc.Flags[+0x100])`.
   5 argomenti oltre al `this` = firma di `ResizeBuffers` → slot `+0x68` confermato dagli argomenti, non solo dall'indice.
   Poi `GetBuffer(0)` (`+0x48`), `GetDesc` texture (`+0x50`), ricrea depth/RT, aggiorna `desc.Width/Height`,
   `OMSetRenderTargets`.

Il resize **non** ricrea il device. Il render thread è fermo durante il resize (sincronizzazione al punto 2).

### Fullscreen / alt-tab / device reset

| Aspetto | Evidenza | Confidence |
|---|---|---|
| `SetFullscreenState(FALSE, NULL)` | solo in shutdown renderer `0x4FEAB0` @ `0x4FEBEB`, prima di `Release` | CONFIRMED |
| `GetFullscreenState` | `0x697C30` (vfunc di game-app, vtable `0x8B53E0`[51]) → `app+0x12AC` | CONFIRMED |
| Toggle fullscreen | nessun `SetFullscreenState(TRUE)` trovato. `0x4F5D90` non chiama `MakeWindowAssociation` (gli altri 2 utenti della factory non verificati) → Alt+Enter probabilmente gestito da DXGI di default. `WM_SYSKEYDOWN` è però intercettato in WndProc: gestione custom possibile | PROBABLE |
| `WM_ACTIVATE` | `0x654D20` → `app->vfunc[0x30]` → `app+0xDA` active, `+0xD9` changed; main loop → `vfunc[0x88]` ("active") | CONFIRMED |
| `WM_SIZE SIZE_MINIMIZED` | globale `0xC59F05 = 1`, `app->vfunc[0x30](0)` | CONFIRMED |
| Device lost / `DXGI_ERROR_DEVICE_REMOVED` | nessuna gestione trovata; `Present` fallito ritorna solo `false` | PROBABLE (assenza) |

## Finestra / WndProc

- `0x651E80`: `RegisterClassA("PhyreFrameworkClass", lpfnWndProc=0x650440)` → `AdjustWindowRect` →
  `CreateWindowExA` (salta la creazione se l'host fornisce già un HWND in `params+0x30`) →
  **HWND → `0xC59F08`** → `SetWindowLongPtrA(hwnd, GWLP_USERDATA, app)` → `RegisterDeviceNotificationA`.
- App object globale: `0xC59F38` (puntatore), scritto dal costruttore `0x64A270` (default 1280×720).
- WndProc `0x650440` (+ chunk `.pdata` chained `0x650491`, `0x6504C4`, `0x650512`): recupera `app` da
  `GWLP_USERDATA`; gestisce `WM_CREATE(1)`, `WM_DESTROY(2)`, `WM_SIZE(5)`, `WM_ACTIVATE(6)`, `WM_CLOSE(0x10)`,
  `WM_ERASEBKGND(0x14)`, `WM_GETMINMAXINFO(0x24)`, `WM_SYSKEYDOWN(0x104)`, `WM_DEVICECHANGE(0x219)`, messaggio
  registrato `"PHYREMSG_HOSTHWND"`; il resto → `DefWindowProcA`.
- **Nessun input in WndProc**: tastiera/mouse sono in polling (vedi `notes.md`, blocco 3). Implica che un
  overlay ImGui deve anche bloccare il polling del gioco, non solo filtrare i messaggi.

Punto più pulito per l'hook WndProc: `SetWindowLongPtrA(HWND@0xC59F08, GWLP_WNDPROC, …)` dopo che la finestra
esiste. Nessuna necessità di patchare codice.

## Oggetto renderer (static `0xBAD540`)

Singleton lazy-init, accessor `0x4F6E30` (guard bit `0xBAECA0`), protetto da lock `0x4E7340`.
Solo offset osservati; nessun nome di campo oltre a quanto dimostrato dall'uso.

| Offset | Uso osservato | Confidence |
|---|---|---|
| +0x94..+0xA0 | 4 dword copiati da `app+0xE08` prima dell'init (dimensioni?) | UNKNOWN (significato) |
| +0xA8 | `ID3D11Device*` | CONFIRMED |
| +0xB0 | `ID3D11DeviceContext*` (immediate) | CONFIRMED |
| +0xB8 | `IDXGISwapChain*` | CONFIRMED |
| +0xC0 | `DXGI_SWAP_CHAIN_DESC` (0x48 B) | CONFIRMED |
| +0x108 | feature level ottenuto | CONFIRMED |
| +0x110 | puntatore a `0xBF7CB8` (formato/descrittore RT?) | UNKNOWN |
| +0x138 / +0x13C | width / height backbuffer (da `GetDesc`) | HIGH CONFIDENCE |
| +0x148 | `ID3D11Texture2D*` backbuffer (array con count in +0x140) | HIGH CONFIDENCE |
| +0x180 | `D3D11_TEXTURE2D_DESC` backbuffer | CONFIRMED |
| +0x250 | oggetto render target backbuffer (RTV via `0x4F6EF0`) | HIGH CONFIDENCE |
| +0x2F8 | oggetto depth target (DSV via `0x4F6A50`) | HIGH CONFIDENCE |
| +0x638 | buffer `DRAWINDIRECT_ARGS` (solo FL ≥ 11_0) | CONFIRMED |
| +0x1740 | byte VSync (SyncInterval) | CONFIRMED |

## Render thread

- Creazione: `0x531F50` → semafori `+0x2C0` (count 16) e `+0x2D0` (count 1), 16 slot, `0x5452B0`
  (wrapper `CreateThread`, stack `0x10000`) con nome `"PhyreEngineRenderThread"`, entry `0x526D10`.
- Loop `0x53F740`: nome thread `"RenderThread"`, ring di 16 command buffer, stato in `+0x28`
  (0 = idle, 1 = esegui, 2 = esci).
- Tutte le chiamate D3D11 del frame passano dal dispatcher `0x531570` (switch su tipo comando, 0x2B case).
  Init, resize e shutdown avvengono invece dal main thread con il render thread fermo/sincronizzato.

## Raccomandazione hook D3D11 per SAOHRFix

**Opzione A (vtable swapchain), con cattura del puntatore reale via IAT.** Non l'opzione B.

1. Da ASI caricato da Ultimate ASI Loader (già funzionante qui): hook dello slot IAT di
   `d3d11!D3D11CreateDeviceAndSwapChain` in `sao_hr.exe` (IAT RVA `0x7FEA88`, è l'unico sito di creazione).
   Se l'ASI arriva dopo la creazione: leggere `IDXGISwapChain*` da `0xBAD5F8` (fallback, build-specific).
2. Sullo swapchain ottenuto: detour (MinHook) delle funzioni puntate da vtable `+0x40 Present` e
   `+0x68 ResizeBuffers`. Non patchare la vtable: con ReShade/Special K lo swapchain può essere un wrapper.
3. `ResizeBuffers` va hookato: il gioco lo chiama davvero (`0x4FAFA9`) → l'overlay deve rilasciare le sue RTV.

Perché non B (`0x4F5F10` o il case del dispatcher):
- Present è un **comando in coda** eseguito dal render thread via jump table: agganciare lì è build-specific
  senza vantaggi, e non intercetta i Present di eventuali altri layer.
- A funziona identico su build diverse, è lo standard atteso dagli altri layer (ReShade/SK) e da ImGui.
- B resta utile solo come *punto di osservazione* (es. timing), non come hook principale.

**Vincolo architetturale (da rispettare in Phase 1):** `Present` gira sul **render thread**, `WndProc` e il
polling input del gioco sul **main thread**. L'overlay ImGui disegnerà sul render thread mentre gli eventi
arrivano sul main thread → serve un passaggio di stato input thread-safe (coda/double buffer), e il blocco
dell'input di gioco quando l'overlay ha il focus va fatto sul main thread.

## Non ancora risolto (rimandato)

- Altri due chiamanti di `CreateDXGIFactory`: `0x166540`, `0x6977C0` (usano anche `CreateShaderResourceView`).
  Probabile enumerazione modalità per il menu opzioni. UNKNOWN, non bloccante.
- Limiter FPS / delta time del main loop → blocco 7.
- Mappa call site creazione risorse → `rendering.md`.
