# Reverse engineering notebook

Solo ipotesi e piste aperte. Quando una pista è confermata → spostarla nel documento
di competenza. Quando è smentita → `REJECTED: motivo`.

Build di riferimento: `sha256 1923f0d8…9e43` (vedi `build.md`).

## Blocco 2 — chiuso, risultati in `graphics.md`

Resta aperto (basso impatto):
- Chiamanti extra di `CreateDXGIFactory`: `0x166540`, `0x6977C0` (usano anche `CreateShaderResourceView`).
  Ipotesi: lista modalità video per il menu opzioni / thumbnail. Non bloccante.
- `WM_SYSKEYDOWN (0x104)` gestito in WndProc: verificare se implementa Alt+Enter custom.
- Globale double `0xBBA9C8` aggiornato dopo ogni Present: candidato "frame time" → blocco 7.
- `0x696020` (game app `animate`, vtable `0x8B53E0`+0x50): se `app+0x12AA` calcola un viewport **16:9
  letterbox/pillarbox** (`w/16` vs `h/9`) in `app+0x11D0..0x11DC`. Quasi certamente il punto patchato dalla
  mod Ultrawide. Delta time letto via `app->vfunc[0xD8]` → blocco 7.

REJECTED: "swapchain creata via `IDXGIFactory::CreateSwapChain`" — creata solo da
`D3D11CreateDeviceAndSwapChain` @ `0x4F7FA3`; la factory serve solo a `GetDisplayModeList`.
REJECTED: `0x35F3C1 call [rax+0x68]` come ResizeBuffers — falso positivo dello scanner (oggetto gameplay).

## Blocco 3 — chiuso lato statico, risultati in `input.md` / `player.md`

Aperte:
- Scopo di `SetWindowsHookExA` (`0x695990`) e del secondo percorso `GetKeyboardState` (`0x68EE20`, `0x6903B0`).
- `RegisterDeviceNotificationA` (`0x6520FA`) + `WM_DEVICECHANGE`: da verificare nel blocco 4 se il filtro copre
  anche endpoint audio (probabilmente solo HID/interfacce).
- Pista animazione (solo metadati di reflection Phyre, uso per il player non dimostrato):
  `PCharacterMotionGait`, `m_gaits`, `m_speedMultiplier`, `m_speedAdjust`, `m_animSpeedLimit`,
  `m_motionAnimSpeedScale`, `m_animIdleSpeedThreshold`, `updateSpeed`, `getCurrentSpeed`, `setMaximumSpeed`.
  Se il player usa `PCharacterAnimationComponent`, `m_speedMultiplier` sarebbe il candidato Sprint ideale
  (velocità + animazione insieme). Verificabile dopo `MOVEMENT-01`.
- `PModifiedBulletKinematicCharacterController::updateAction` override `0x58D340`: punto dove Phyre integra dt.
- Stringhe interessanti per l'animazione del gioco: `sysMotion`, `CChrMotion`, `CChrModelBaseMot`.

REJECTED: "controller Xbox gestito come device DirectInput generico" — la callback di enumerazione `0x64E250`
accetta solo `DI8DEVTYPE_MOUSE (0x12)` e `DI8DEVTYPE_KEYBOARD (0x13)`.
REJECTED (build.md, blocco 1): "ASLR attivo" — relocation strippate, modulo sempre a `0x140000000`.

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
- Il lookup passa da CRI File System — `CriFsBinder/PCx64 Ver.1.02.70` (CONFIRMED, RVA
  `0x8D31E1`). Stringhe che nominano esplicitamente le API: `CriFsBinder_GetWorkSizeBindCpk`
  (RVA `0x8D35E0`, `0x8D4B00`), `BindFiles::` (RVA `0x8D36C8`), `criFs_InitializeLibrary` /
  `criFs_FinalizeLibrary` (RVA `0x8D3020`).
- Il punto di intercetto naturale per un VFS futuro è **il binder CRI**, non `CreateFileW`.
  `BindCpk` e `BindFiles` sono presenti; **`criFsBinder_BindDirectory` non compare in nessuna
  stringa** → `UNKNOWN` se sia linkata (l'assenza di una stringa d'errore non prova l'assenza
  della funzione, ma non la si può dare per scontata). Il meccanismo di priorità fra binder
  va verificato, non assunto: finché non lo è, il punto di intercetto del VFS è **indeterminato**.
  Fallback sempre disponibile: hook su `CreateFileA/W` + `ReadFile` (grossolano ma certo).
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
