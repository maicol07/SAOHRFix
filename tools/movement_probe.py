"""Resolve CChrPc -> physics ID -> KCC, then sample without attaching a debugger.

Usage: movement_probe.py <pid> <CChrPc-VA> <seconds> <label>
Only summary statistics leave the process. Reads across objects are not atomic.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import struct
import statistics
import time

from runtime_read import BASE, ProcessReader


def resolve(reader: ProcessReader, pc: int) -> tuple[int, int, int]:
    if struct.unpack("<Q", reader.read(pc, 8))[0] != BASE + 0x80AE08:
        raise ValueError(f"Not a CChrPc primary vtable at 0x{pc:X}")
    physics_id = struct.unpack("<i", reader.read(pc + 0x9FCC, 4))[0]
    if physics_id < 0:
        raise ValueError("CChrPc has no active physics ID; load a playable save")
    global_object = struct.unpack("<Q", reader.read(BASE + 0xB148B8, 8))[0]
    manager = struct.unpack("<Q", reader.read(global_object, 8))[0]
    array = struct.unpack("<Q", reader.read(manager + 0x18, 8))[0]
    count = struct.unpack("<i", reader.read(manager + 0x134, 4))[0]
    if not 0 < count <= 32768:
        raise ValueError(f"Unexpected physics entry count: {count}")
    entries = struct.unpack(f"<{count}Q", reader.read(array, count * 8))
    matches = [entry for entry in entries if entry and
               struct.unpack("<i", reader.read(entry, 4))[0] == physics_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one physics record for ID {physics_id}, got {len(matches)}")
    wrapper = matches[0] + 0x10
    kcc = struct.unpack("<Q", reader.read(wrapper + 0x148, 8))[0]
    if struct.unpack("<Q", reader.read(kcc, 8))[0] != BASE + 0x879BD0:
        raise ValueError(f"Unexpected KCC vtable at 0x{kcc:X}")
    if struct.unpack("<Q", reader.read(kcc + 0xF0, 8))[0] != wrapper:
        raise ValueError("KCC owner does not match physics wrapper")
    return physics_id, wrapper, kcc


def sample(reader: ProcessReader, pc: int, seconds: float, label: str) -> None:
    physics_id, wrapper, kcc = resolve(reader, pc)
    print(json.dumps({"label": label, "pc": hex(pc), "physics_id": physics_id,
                      "wrapper": hex(wrapper), "kcc": hex(kcc), "status": "sampling"}), flush=True)
    start_position = struct.unpack("<4f", reader.read(pc + 0x9DE0, 16))
    start = time.monotonic()
    count = moving = 0
    peak = 0.0
    first_moving: float | None = None
    last_moving: float | None = None
    vectors: Counter[tuple[float, float, float, float]] = Counter()
    factors: Counter[float] = Counter()
    ratios: list[float] = []
    scales: list[float] = []
    magnitudes: list[float] = []
    horizontal: list[float] = []
    movement_scalars: list[float] = []
    while time.monotonic() - start < seconds:
        if struct.unpack("<i", reader.read(pc + 0x9FCC, 4))[0] != physics_id:
            raise ValueError("Physics ID changed during capture; discard this scenario")
        vector = struct.unpack("<4f", reader.read(kcc + 0x50, 16))
        factor = struct.unpack("<f", reader.read(wrapper + 0xF4, 4))[0]
        requested = struct.unpack("<4f", reader.read(wrapper + 0x40, 16))
        velocity = struct.unpack("<4f", reader.read(kcc + 0x100, 16))
        if not all(math.isfinite(v) for v in (*vector, factor, *requested, *velocity)):
            raise ValueError("Non-finite vector or scaling factor during capture")
        magnitude = math.hypot(*vector[:3])
        velocity_magnitude = math.hypot(*velocity[:3])
        requested_magnitude = math.hypot(*requested[:3])
        if magnitude > 1e-5:
            moving += 1
            magnitudes.append(magnitude)
            horizontal.append(math.hypot(vector[0], vector[2]))
            movement_scalars.append(struct.unpack("<f", reader.read(pc + 0x9F24, 4))[0])
            last_moving = time.monotonic() - start
            if first_moving is None:
                first_moving = last_moving
            if velocity_magnitude > 1e-5:
                ratios.append(magnitude / velocity_magnitude)
            if requested_magnitude > 1e-5:
                scales.append(velocity_magnitude / requested_magnitude)
        peak = max(peak, magnitude)
        vectors[vector] += 1
        factors[factor] += 1
        count += 1
        time.sleep(0.01)
    if resolve(reader, pc) != (physics_id, wrapper, kcc):
        raise ValueError("Controller relationship changed during capture")
    print(json.dumps({"label": label, "samples": count, "elapsed_s": time.monotonic() - start,
                      "nonzero": moving, "first_moving_s": first_moving,
                      "last_moving_s": last_moving, "max_magnitude": peak,
                      "median_magnitude": statistics.median(magnitudes) if magnitudes else None,
                      "median_horizontal": statistics.median(horizontal) if horizontal else None,
                      "median_pc_9F24": statistics.median(movement_scalars) if movement_scalars else None,
                      "median_walk_to_velocity_ratio": statistics.median(ratios) if ratios else None,
                      "walk_to_velocity_ratio_range": [min(ratios), max(ratios)] if ratios else [],
                      "velocity_to_request_ratio_range": [min(scales), max(scales)] if scales else [],
                      "common_vectors": vectors.most_common(8), "common_factors": factors.most_common(8),
                      "start_position": start_position,
                      "end_position": struct.unpack("<4f", reader.read(pc + 0x9DE0, 16))}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("pc", type=lambda s: int(s, 0))
    parser.add_argument("seconds", type=float)
    parser.add_argument("label")
    args = parser.parse_args()
    if args.pid <= 0 or args.pc <= 0 or not math.isfinite(args.seconds) or not 0 < args.seconds <= 60:
        parser.error("positive PID/PC and capture duration 0..60 seconds required")
    reader = ProcessReader(args.pid)
    try:
        sample(reader, args.pc, args.seconds, args.label)
    finally:
        reader.close()


if __name__ == "__main__":
    main()
