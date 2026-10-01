"""Bounded polling of internal axes and locomotion. Not an atomic frame snapshot.

Usage: analog_probe.py PID CChrPc-VA seconds
Records share an interval timestamp; ring changes during reads are discarded.
No process writes, remote calls, breakpoints or input generation.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
import statistics
import struct
import sys
import time

from movement_probe import resolve
from runtime_read import BASE, ProcessReader


def selector_result(player: bytes) -> int:
    if struct.unpack_from("<Q", player, 0xA9E0 - 0x9DE0)[0] != BASE + 0x80A8F0:
        raise ValueError("Unexpected embedded selector vtable")
    return int(player[0xA9E9 - 0x9DE0] == 0xFF and player[0xA9F0 - 0x9DE0] == 0xFE)


def sample(reader: ProcessReader, pc: int, seconds: float) -> None:
    identity = resolve(reader, pc)
    _, wrapper, kcc = identity
    start = time.monotonic()
    groups: dict[tuple[int, int, int, int, int], list[tuple[float, ...]]] = defaultdict(list)
    transitions: list[dict[str, object]] = []
    previous: tuple[int, int, int, int, int] | None = None
    rejected = 0
    max_span = 0.0
    positions: list[tuple[float, float, float, float]] = []
    motion_requests: Counter[tuple[int, int, int, float]] = Counter()
    print(json.dumps({"status": "sampling", "identity": identity}), flush=True)
    while time.monotonic() - start < seconds:
        before = time.monotonic_ns()
        mode, _, cursor = struct.unpack("<3i", reader.read(BASE + 0xC69060, 12))
        if mode not in (0, 64) or not 0 <= cursor <= 64:
            raise ValueError(f"Unexpected input ring metadata: {mode}, {cursor}")
        slot = (cursor - 1) % 64 if mode else 0
        axes = struct.unpack("<2h", reader.read(BASE + 0xC66D60 + slot * 0x8C + 0x80, 4))
        player = reader.read(pc + 0x9DE0, 0xF8AE - 0x9DE0)
        motion = reader.read(pc + 0x90F0, 20)
        physics = reader.read(kcc + 0x50, 16)
        pre = struct.unpack("<4f", reader.read(wrapper + 0x40, 16))
        scale = struct.unpack("<f", reader.read(wrapper + 0xF4, 4))[0]
        velocity = struct.unpack("<4f", reader.read(kcc + 0x100, 16))
        dt, _, step = struct.unpack("<3f", reader.read(BASE + 0xA63238, 12))
        after_cursor = struct.unpack("<i", reader.read(BASE + 0xC69068, 4))[0]
        after = time.monotonic_ns()
        max_span = max(max_span, (after - before) / 1e6)
        if cursor != after_cursor:
            rejected += 1
            continue
        # This is the statically reconstructed predicate, not a function call.
        selector = selector_result(player)
        key = (*axes, selector, player[0xF8A6 - 0x9DE0], player[0xF8AD - 0x9DE0])
        speed = struct.unpack_from("<f", player, 0x9F24 - 0x9DE0)[0]
        motion_requests[(key[3], key[4], struct.unpack_from("<h", motion, 8)[0],
                         struct.unpack_from("<f", motion)[0])] += 1
        vec = struct.unpack("<4f", physics)
        magnitude = math.hypot(vec[0], vec[2])
        groups[key].append((speed, dt, magnitude, step, math.hypot(pre[0], pre[2]),
                            scale, math.hypot(velocity[0], velocity[2]),
                            magnitude / dt if dt > 0 else 0.0))
        position = struct.unpack_from("<4f", player, 0)
        positions.append(position)
        if key != previous:
            transitions.append({"t": (before / 1e9) - start, "axes_selectors": key,
                                "speed": speed, "step": step})
            previous = key
        time.sleep(0.01)
    if resolve(reader, pc) != identity:
        raise ValueError("Player physics identity changed during capture")
    if not positions:
        raise ValueError("No stable input-ring record acquired during capture")
    print(json.dumps({"elapsed": time.monotonic() - start, "atomic": False,
                      "rejected_ring_changes": rejected, "max_read_span_ms": max_span,
                      "start": positions[0], "end": positions[-1],
                      "transitions": transitions[:100], "transition_count": len(transitions),
                      "motion_requests": [{"F8A6": key[0], "F8AD": key[1],
                                           "request_id": key[2], "rate_candidate": key[3], "samples": count}
                                          for key, count in motion_requests.most_common(30)],
                      "groups": [{"axes_selectors": key, "samples": len(values),
                                  "median_speed": statistics.median(v[0] for v in values),
                                  "median_dt": statistics.median(v[1] for v in values),
                                  "median_kcc_xz": statistics.median(v[2] for v in values),
                                  "median_step": statistics.median(v[3] for v in values),
                                  "median_pre_xz": statistics.median(v[4] for v in values),
                                  "median_wrapper_scale": statistics.median(v[5] for v in values),
                                  "median_velocity_xz": statistics.median(v[6] for v in values),
                                  "median_kcc_per_dt": statistics.median(v[7] for v in values)}
                                 for key, values in sorted(groups.items())]}))


def main() -> None:
    if sys.argv[1:] == ["self-check"]:
        player = bytearray(0xF8AE - 0x9DE0)
        struct.pack_into("<Q", player, 0xA9E0 - 0x9DE0, BASE + 0x80A8F0)
        player[0xA9E9 - 0x9DE0], player[0xA9F0 - 0x9DE0] = 0xFF, 0xFE
        assert selector_result(bytes(player)) == 1
        player[0xA9E9 - 0x9DE0] = 0
        assert selector_result(bytes(player)) == 0
        print("self-check passed")
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("pc", type=lambda s: int(s, 0))
    parser.add_argument("seconds", type=float)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 120:
        parser.error("seconds must be finite and within 0..120")
    reader = ProcessReader(args.pid)
    try:
        sample(reader, args.pc, args.seconds)
    finally:
        reader.close()


if __name__ == "__main__":
    main()
