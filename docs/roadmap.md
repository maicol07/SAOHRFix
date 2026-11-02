# Historical roadmap

Research and development are discontinued because the author finished the game
and does not want to spend more time on the project. This plan is retained for
context, not as a commitment to implement the remaining features.

## Phase 0, reverse engineering and reconnaissance

| Block | Area | Existing output | Final status |
|---|---|---|---|
| 1 | Build identification and imports | `reversing/build.md` | Completed within documented scope |
| 2 | D3D11 and render loop | `reversing/graphics.md` | Completed within documented scope |
| 3 | Input and player movement | `reversing/input.md`, `reversing/player.md`, `reversing/movement-report.md` | Extensive static/runtime research; SLOPE-07B approved a first Sprint implementation, not production safety |
| 4 | Audio, CRI ADX2 / WASAPI | No dedicated report | Not started |
| 5 | Filesystem/loading, CPK | No dedicated report | Not started |
| 6 | Render targets/buffers | Preliminary `reversing/rendering.md` | Temporal readiness not established |
| 7 | Camera and timing | Findings within existing reports | No completed dedicated reports |
| 8 | Consolidation | This archive and the existing reports | No original Phase 0 completion report |

The research reporting rule was to separate what is known, what is unknown,
the best current hypothesis and the cheapest useful next test.

## Unfinished native Sprint preview

SPRINT-01/01B added a native Windows x64 loader/core, configuration, input logic,
hooks and A+C movement prototype. Debug/Release build, but no native Sprint extra
was accepted in the live tests. See [sprint-01.md](sprint-01.md) for the exact
parameter guard, L3/UI limits and Debug initialization issue.

## Proposed later phases, not completed

- Phase 1: SAOHRFix framework, Present hook, ImGui overlay and configuration.
- Phase 2: gameplay/QoL, Sprint, FOV, camera distance and audio-device hot swap.
- Phase 3: filesystem, asset overrides through a VFS, caching/prefetch and loading.
- Phase 4: graphics, remastered assets and DLAA/DLSS/FSR/XeSS.
- Phase 5: experimental D3D12 bridge, Frame Generation and ray tracing.

These proposals depend on research that was never completed. Their presence in
the roadmap does not imply implementation, compatibility or readiness.
