# Roadmap

## Phase 0 — Reverse engineering & reconnaissance (in corso)

Blocchi, nell'ordine di esecuzione:

| # | Blocco | Output | Stato |
|---|---|---|---|
| 1 | Build identification + imports | `reversing/build.md` | ✅ fatto |
| 2 | D3D11 / render loop | `reversing/graphics.md` | ✅ fatto |
| 3 | Input + player movement | `reversing/input.md`, `reversing/player.md` | ⬜ |
| 4 | Audio (CRI ADX2 / WASAPI) | `reversing/audio.md` | ⬜ |
| 5 | Filesystem / loading (CPK) | `reversing/filesystem.md`, `reversing/loading.md` | ⬜ |
| 6 | Render target / buffer | `reversing/rendering.md`, `reversing/temporal-readiness.md` | ⬜ |
| 7 | Camera + timing | `reversing/camera.md`, `reversing/timing.md` | ⬜ |
| 8 | Consolidamento | `phase-0-report.md` | ⬜ |

Definition of Done: vedi §20 del brief — per ogni area serve *cosa sappiamo / cosa non
sappiamo / migliore ipotesi / test successivo più economico*.

## Fasi successive (non iniziare in Phase 0)

- **Phase 1** — framework SAOHRFix: loader, hook Present, overlay ImGui, config.
- **Phase 2** — gameplay/QoL: sprint, FOV, camera distance, hot-swap audio device.
- **Phase 3** — filesystem: VFS con override asset, cache/prefetch, fast loading.
- **Phase 4** — grafica: remaster asset, DLAA/DLSS/FSR/XeSS.
- **Phase 5** — sperimentale: bridge D3D12, Frame Generation, ray tracing.

Ogni fase dipende da risposte prodotte in Phase 0; niente implementazione finché l'area
corrispondente non è almeno `HIGH CONFIDENCE`.
