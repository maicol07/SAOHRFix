# SAOHRFix

PC/Steam Hollow Realization reverse engineering, Phase 0. Python 3.14 in `.venv`,
pefile/Capstone, PowerShell tools. Existing Git history and `docs/reversing/` are
the technical baseline. Use RVAs plus verified build-local signatures.

- Stay on the current branch. Commit only with explicit user authorization.
- Read the applicable existing tools/docs before adding code; keep diffs scoped.
- Never patch `sao_hr.exe` permanently, edit CPK archives, or commit proprietary
  bytes, executables, large captures, downloaded binaries or process dumps.
- Label evidence CONFIRMED / HIGH CONFIDENCE / PROBABLE / UNKNOWN and distinguish
  static analysis from runtime observations. Heap addresses are session-only.
- Runtime vanilla: reversibly disable local mods with `tools/mods.ps1`, stop
  global injection via SKIF, launch via Steam. Preserve and restore prior state.
- Prefer read-only process inspection. No automatic invasive anti-debug bypass.
- Current task is MOVEMENT-01/02. No Audio, Sprint implementation, INPUT-01 or
  STATE-01 until the movement prerequisites are satisfied.

Current findings are in `docs/reversing/movement-report.md` and `player.md`.
Virtual Xbox input works through Steam with the existing ViGEmBus; use
`virtual_pad.py` rather than asking for imprecise physical stick positions.
Its percentages are not the internal axis values: measure consumed input.
`analog_probe.py` polls bounded read intervals, never atomic frames.
`walk_trace.py` is explicitly authorized temporary diagnostic instrumentation:
player/KCC/animation-channel instance vtables only, original calls preserved,
restoration required. `run_perturb.py` is an authorized diagnostic only;
live-tested at 1.10/1.25, with exact historical bits 3E2BB98D (not float32(0.1677)).
Its bounded --baseline-bits also accepts observed 3E2D712B; measure vanilla first.
`fps_limit.py` temporarily changes an existing NVIDIA app profile,
restores its original setting on exit, and requires game restart for cap changes.
Its sequential records and cross-thread production copies are not atomic frames.
Speed threshold and physical submission callers are identified. Actual movement
at externally observed 30/120 FPS is consistent; cap 60 lacks external FPS
verification. Animation is Case B: run downstream rate stays 1 with faster
movement. A 1.25 wall test produced a large vertical excursion absent from a
nearby vanilla comparison; newer Anticamera captures supersede that comparison.
Earlier controlled wall captures: 1.25 has four stable runs; one of three
effective 1.10 runs ascends through original caller 1F625A, parameter 0.5,
clip 246 and an already-positive requested Y. Static parent 1F5B30 compares
query height/normal, A025, negative 9F58, 9FDC*pi/180 and 9FF8<600;
1F625A calls +428 -> 20D0C0 -> 2C4450, selecting state 4 request 206/246.
TRACE-246-01 shim rejection and trigger body are now live-tested. The original
1F625A/246 path preserves parameter 0.5 and clip rate 1; Sprint excludes it.
Anticamera captures also show large ascents through ordinary 1E993F/122,
A025=0 and no special calls, at 1.10/1.15/1.25; five vanilla controls stable.
Three stable 1.20 captures do not prove a safe threshold. COLLISION-SLOPE-01
synchronized trace localizes forward projection 72B3C0 -> target Y 72B5EA;
v-dot(v,n)*n matches a negative requested Y becoming positive actual dY.
Movement-only 1.15 reaches Y=14.218; preStep recovery is unchanged during high
ascents. Experimental post-contact suppression latches and restores vanilla
speed/rate, but still reaches Y=4.656: not a validated safety mechanism.
COLLISION-SLOPE-02 native threshold is KCC+38 = cos(KCC+34), not +9FDC;
closest callback 729DA5 rejects threshold > dot(up, normal).
Pre-projection 72ACC8 deboost/latch passes three 1.15 trials but one of two
1.25 trials reaches Y=12.982. First bad seq481 has positive requested Y,
no new forward hit, latch off, +C0=1 and cached +D0 matching recovery 72AB3C.
COLLISION-SLOPE-03 directly traces cached recovery 72AB3C. C0 resets each
preStep and means penetration corrected; D0 can remain stale with C0=0.
Cached normal points inward; native recovery requires dot(direction60,D0)>0.
Producer input/integrated Y stays current while gameplay target/request Y
changes before KCC; surface preparation 1F5B30 is the high-confidence source.
Cached suppression before 1E9980 fails: initial recovery calls read vanilla
parameter but still ascend, then C0=0 releases the gate and boost resumes.
COLLISION-SLOPE-04 directly identifies query-fed target Y store 1F5E15 and
requested Y call 1F663D -> component store 16488F. Vanilla-first A+C keeps
the original locomotion parameter, then optionally adds a native capsule-
preflighted physical substep; flat extra is 25%, with owner sync observed.
Two trials avoid the large ascent, but the second reaches Y=1.704 versus
vanilla controls near 1.595, during the first native step with no extra.
Causality is unresolved; the sole blocker is first-contact equivalence and
stability after earlier extras. No production Sprint; see SLOPE-04 for limits.
SKIF native Stop/Start resolved its inaccessible UI on 2026-10-02. The user
identified the historical lane as Anticamera delle Grandi Pianure Rastoria.
Direct teleport to Anticamera is verified from the Rustoria regional map;
near-historical XYZ and wall geometry verified. Pad resets are bounded, not
bit-identical; use the report's exact starts and exclusions. mods.ps1 regex corrected.
Animation return perturbation is player-channel-only, clip 122 only; factor
1.25 best matches baseline distance/phase, but direct foot sliding is unmeasured.
Selector 1 / parameter 0.109005 / clip 100122 is outside the verified FF/FE
context and must not count as an effective multiplier test. Lifecycle transitions,
tight turns, slopes/stairs and town/combat remain deferred. Sprint is NOT READY.
Runtime clamps are 0/60; actual world position is Bullet ghost+40. Downstream
animation rate getter 6C6C80 -> 2888CC -> channel+1D0 -> 56E530 identified.
Run each new tool's `self-check` before live use; never install drivers implicitly.
