# Reverse engineering notebook

Solo ipotesi e piste aperte. Quando una pista è confermata → spostarla nel documento
di competenza. Quando è smentita → `REJECTED: motivo`.

Build di riferimento: `sha256 1923f0d8…9e43` (vedi `build.md`).

## Aperte — blocco 2 (D3D11 / render loop)

- L'import è `dxgi!CreateDXGIFactory` (v1 legacy) + `d3d11!D3D11CreateDeviceAndSwapChain`.
  Ipotesi: swapchain creata in un unico punto tramite `D3D11CreateDeviceAndSwapChain`, non
  tramite `IDXGIFactory::CreateSwapChain`. Da verificare disassemblando gli xref all'IAT.
  → Se confermato, il `Present` si raggiunge solo via vtable della swapchain (hook standard).
- Cercare xref a `D3D11CreateDevice` (import separato) — potrebbe essere un fallback o un
  percorso di device di capability check.
- Feature level richiesto: UNKNOWN. Determina se un bridge D3D12 futuro è realistico.

## Aperte — blocco 3 (input)

- Solo `DINPUT8!DirectInput8Create` + 45 import `USER32`. **Nessun XInput e nessun Raw Input**
  (`RegisterRawInputDevices`/`GetRawInputData` assenti dalla lista completa USER32) — CONFIRMED.
- Tastiera/mouse sono in **polling**: `GetKeyboardState`, `GetKeyState`, `GetCursorPos`,
  `ScreenToClient`. Nessun `GetAsyncKeyState`.
- Message loop classico: `RegisterClassA` + `CreateWindowExA` + `PeekMessageA` /
  `TranslateMessage` / `DispatchMessageA` / `DefWindowProcA` → **WndProc sostituibile con
  `SetWindowLongPtrA(GWLP_WNDPROC)`**, che il gioco stesso già usa (import presente).
  Percorso pulito per l'input di una futura overlay ImGui.
- `RegisterDeviceNotificationA` presente → il gioco reagisce all'hotplug dei device.
  Vale la pena controllare se la stessa notifica copre anche i device audio (improbabile ma
  a costo zero da verificare sugli xref).
- `SetWindowsHookExA` / `UnhookWindowsHookEx` / `CallNextHookEx` presenti: da capire quale
  hook installa (probabile `WH_KEYBOARD`/`WH_GETMESSAGE` per l'IME, visti gli import IMM32).
- Ipotesi: controller Xbox gestito come device DirectInput generico → spiegherebbe le
  segnalazioni storiche di mapping pulsanti anomalo su questo titolo. Non confermato.
- PhyreEngine ha un layer `PInput`/`PPad` proprio: cercare stringhe `PInput`, `PPad`.

## Aperte — blocco 4 (audio) — pista forte

- Backend confermato a livello di libreria: CRI ADX2, renderer ASR, output **WASAPI**
  (`CRI NcVoice WASAPI/PCx64 Ver.1.25.00`).
- `ole32!CoCreateInstance` è quasi certamente `IMMDeviceEnumerator` dentro NcVoice.
- Stringhe di errore utili come ancore AOB/xref per trovare le funzioni di init:
  - `W2014021962:WASAPI is not available. Atom library operates without sound output.`
    (RVA `0x8D0AD0`)
  - `E2013042461:WASAPI has been finalized though some handles are still active.`
    (RVA `0x8D0B30`)
  - `E2016012822:CRI Atom ASR must be initialized when sound render type is set to
    CRIATOM_SOUND_RENDERER_ASR`
- Ipotesi per l'hot-swap del device: CRI Atom espone già un ciclo
  `criAtom_Finalize` → `criAtom_Initialize` / `criAtomAsr_Initialize`. Se il gioco lo
  richiama in un unico punto, il fix è: `IMMNotificationClient` → chiama quel path.
  **Alternativa meno invasiva da valutare per prima**: hookare `IAudioClient::Initialize`
  o intercettare la creazione dell'endpoint dentro NcVoice e forzare il re-init lì.
- Da verificare: se NcVoice apre l'endpoint in modalità shared con `eRender/eConsole` e se
  gestisce già `AUDCLNT_E_DEVICE_INVALIDATED` (esiste una stringa di errore corrispondente?).

## Aperte — blocco 5 (filesystem / loading) — pista forte

- `pkg/data.cpk` (RVA `0x801A80`) e `pkg/%s.cpk` (RVA `0x801A90`) sono gli unici path di
  archivio hardcoded. Il `%s` è il codice lingua (`ita`, `usa`, `ger`, …) — coerente con i
  file in `pkg/`.
- Il lookup passa da CRI File System (`criFsBinder_BindCpk` / `criFsLoader_Load`).
  Il punto di intercetto naturale per un VFS futuro è **il binder CRI**, non `CreateFileW`:
  CRI FS supporta nativamente un binder di directory con priorità maggiore del CPK
  (`criFsBinder_BindDirectory`). Da verificare se le funzioni sono raggiungibili.
- Asset naming: stringhe tipo `custom_chr_tone.fx#CA68C990DF8603BDFDE0BB809E8C0570.phyre`
  suggeriscono che gli shader siano indicizzati per hash MD5-like del contenuto/permutazione.
  Da qui probabilmente anche l'uso di `ADVAPI32` CryptoAPI (hashing).
- `%s%s.phyre` (RVA `0x827EA8`) → composizione di nome asset a runtime = buon candidato
  come punto di intercetto per l'override.

## Aperte — blocco 6/7 (rendering, camera, timing)

- Stringhe di shader trovate: `/Shaders/prim_shader.fx.phyre`, `prim_shader_tex`,
  `prim_shader_zpre` (**z-prepass**), `prim_shader_effect`, `/sys/dith_mask.dds.phyre`.
  `zpre` implica un depth prepass → depth buffer completo disponibile presto nel frame.
- Da `dlss5-feed.log` (HIGH CONFIDENCE, ma **processo moddato**): swapchain in
  `sRGB G2.2 BT.709 (SDR)`, window class `PhyreFrameworkClass`, `depth reversed=1`.
  → Nessun HDR path. Depth reversed-Z: rilevante per qualunque uso temporale futuro.
- Motion vectors: nessuna evidenza. PhyreEngine base non ha un G-buffer velocity standard.
  Presunzione di partenza: **assenti** → un futuro DLSS/FSR richiederebbe di generarli.
- `WINMM!timeBeginPeriod` + `QueryPerformanceCounter` + fiber → loop di gioco con timer ad
  alta risoluzione. Il cap a 60 FPS del titolo è UNKNOWN: potrebbe essere `SyncInterval=1`
  in `Present` oppure un limiter interno. Test più economico: disassemblare la call a
  `Present` e leggere il valore di `SyncInterval`.

## Smentite

*(nessuna finora)*
