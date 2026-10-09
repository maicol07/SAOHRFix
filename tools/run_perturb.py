"""Temporary player-only run parameter perturbation at the verified setter.

Usage: run_perturb.py PID CChrPc-VA seconds factor
Only bounded diagnostic factors, observed exploration run branch and caller pair.
Instance vptrs restored by walk_trace; no permanent game patch or global write.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time

from runtime_read import BASE, ProcessReader
from walk_trace import producer_shim, rate_shim, trace

RUN_BASELINES = (0x3E2BB98D, 0x3E2D712B)


def perturb_shim(log: int, original: int, pc: int, physics_id: int, factor: float,
                 baseline_bits: int = 0x3E2BB98D,
                 suppression_address: int | None = None) -> bytes:
    if baseline_bits not in RUN_BASELINES:
        raise ValueError("Only captured exploration run baselines allowed")
    if factor not in (1.00, 1.10, 1.15, 1.20, 1.25):
        raise ValueError("Only 1.00/1.10/1.15/1.20/1.25 diagnostic factors allowed")
    code = bytearray.fromhex("9C 50 41 52 49 BA") + struct.pack("<Q", pc)
    jumps: list[int] = []

    def require_equal(instructions: bytes) -> None:
        code.extend(instructions)
        code.extend(bytes.fromhex("0F 85 00 00 00 00"))
        jumps.append(len(code) - 4)

    require_equal(bytes.fromhex("4C 39 D1"))  # rcx must be the resolved player
    require_equal(bytes.fromhex("41 81 BA CC 9F 00 00") + struct.pack("<i", physics_id))
    for offset, value in ((0xF8A6, 1), (0xF8AD, 0), (0xA9E9, 0xFF), (0xA9F0, 0xFE)):
        require_equal(bytes.fromhex("41 80 BA") + struct.pack("<iB", offset, value))
    for stack_offset, caller in ((0x18, BASE + 0x1E993F), (0xA8, BASE + 0x206660)):
        code.extend(bytes.fromhex("48 8B 84 24") + struct.pack("<i", stack_offset))
        code.extend(bytes.fromhex("49 BA") + struct.pack("<Q", caller))
        require_equal(bytes.fromhex("4C 39 D0"))
    # Match the captured original exactly; do not broaden the run branch guard.
    require_equal(bytes.fromhex("66 0F 7E D0 3D") + struct.pack("<I", baseline_bits))
    if suppression_address is not None:
        code.extend(bytes.fromhex("49 BA") + struct.pack("<Q", suppression_address))
        require_equal(bytes.fromhex("41 83 3A 00"))
    code.extend(bytes.fromhex("B8") + struct.pack("<f", factor))
    code.extend(bytes.fromhex("50 F3 0F 59 14 24 58"))  # multiply incoming xmm2 only
    restore = len(code)
    code.extend(bytes.fromhex("41 5A 58 9D"))
    for displacement in jumps:
        struct.pack_into("<i", code, displacement, restore - displacement - 4)
    code.extend(producer_shim(log, original))
    return bytes(code)


def animation_rate_shim(log: int, original: int, pc: int, physics_id: int,
                        owner: int, controller: int, channel: int,
                        movement_factor: float, animation_factor: float,
                        baseline_bits: int = 0x3E2BB98D,
                        suppression_address: int | None = None) -> bytes:
    if baseline_bits not in RUN_BASELINES:
        raise ValueError("Only captured exploration run baselines allowed")
    if animation_factor not in (1.10, 1.15, 1.20, 1.25):
        raise ValueError("Unsupported diagnostic animation factor")
    guard = bytearray()
    jumps: list[int] = []

    def reject(instructions: bytes, branch: int = 0x85) -> None:
        guard.extend(instructions + bytes((0x0F, branch)) + b"\0" * 4)
        jumps.append(len(guard) - 4)

    guard.extend(bytes.fromhex("49 BA") + struct.pack("<Q", log + 0x100))
    reject(bytes.fromhex("41 80 3A 01"))
    guard.extend(bytes.fromhex("48 8B 44 24 20 49 BA") + struct.pack("<Q", BASE + 0x2888CC))
    reject(bytes.fromhex("4C 39 D0"))
    guard.extend(bytes.fromhex("49 BA") + struct.pack("<Q", pc))
    reject(bytes.fromhex("41 81 BA CC 9F 00 00") + struct.pack("<i", physics_id))
    for offset, value in ((0xF8A6, 1), (0xF8AD, 0), (0xA9E9, 0xFF), (0xA9F0, 0xFE)):
        reject(bytes.fromhex("41 80 BA") + struct.pack("<iB", offset, value))
    baseline = struct.unpack("<f", struct.pack("<I", baseline_bits))[0]
    reject(bytes.fromhex("41 81 BA 24 9F 00 00") + struct.pack("<f", baseline * movement_factor))
    for address, offset, expected in ((pc, 0x4C0, owner), (owner, 0x108, controller),
                                      (controller, 0x2F0, channel)):
        guard.extend(bytes.fromhex("49 BA") + struct.pack("<Q", address))
        guard.extend(bytes.fromhex("48 B8") + struct.pack("<Q", expected))
        reject(bytes.fromhex("49 39 82") + struct.pack("<i", offset))
    reject(bytes.fromhex("48 39 C1"))  # actual instance equals current channel zero
    reject(bytes.fromhex("66 0F 7E C0 3D 00 00 80 3F"))  # original run rate is 1
    guard.extend(bytes.fromhex("44 8B 99 14 01 00 00"))
    reject(bytes.fromhex("45 85 DB"), 0x88)  # negative active clip index
    reject(bytes.fromhex("44 3B 99 B8 00 00 00"), 0x8D)
    guard.extend(bytes.fromhex("4C 8B 91 A8 00 00 00"))
    reject(bytes.fromhex("4D 85 D2"), 0x84)
    guard.extend(bytes.fromhex("49 6B C3 28"))  # descriptor stride is 40
    reject(bytes.fromhex("41 81 7C 02 18") + struct.pack("<i", 122))
    reject(bytes.fromhex("44 3B 99 14 01 00 00"))  # index must still match
    if suppression_address is not None:
        guard.extend(bytes.fromhex("49 BA") + struct.pack("<Q", suppression_address))
        reject(bytes.fromhex("41 83 3A 00"))
    guard.extend(bytes.fromhex("B8") + struct.pack("<f", animation_factor))
    guard.extend(bytes.fromhex("50 F3 0F 59 04 24 58"))
    for displacement in jumps:
        struct.pack_into("<i", guard, displacement, len(guard) - displacement - 4)
    original_code = rate_shim(log, original)
    split = original_code.index(bytes.fromhex("66 0F 7E C0 49 BA"))
    return original_code[:split] + guard + original_code[split:]


def main() -> None:
    if sys.argv[1:] == ["self-check"]:
        import capstone
        code = perturb_shim(0x12341A00, BASE + 0x1E9980, 0x213F9890, 10, 1.10)
        instructions = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(code[:-8], 0))
        assert sum(i.size for i in instructions) == len(code) - 8
        assert len(code) <= 0x200
        targets = {i.op_str for i in instructions if i.mnemonic == "jne"}
        assert len(targets) == 1 and len([i for i in instructions if i.mnemonic == "jne"]) == 9
        assert len([i for i in instructions if i.mnemonic == "mulss"]) == 1
        assert bytes.fromhex("3D 8D B9 2B 3E") in code
        observed = perturb_shim(0x12341A00, BASE + 0x1E9980, 0x213F9890, 10,
                                1.25, 0x3E2D712B)
        assert bytes.fromhex("3D 2B 71 2D 3E") in observed
        rate = animation_rate_shim(0x12341E00, BASE + 0x6C6C80, 0x213F9890,
                                   10, 0x22000000, 0x23000000, 0x24000000,
                                   1.25, 1.25, 0x3E2D712B)
        expected = struct.pack("<f", struct.unpack("<f", struct.pack("<I", 0x3E2D712B))[0] * 1.25)
        assert bytes.fromhex("41 81 BA 24 9F 00 00") + expected in rate
        for factor in (1.00, 1.10, 1.15, 1.20, 1.25):
            assert len(perturb_shim(0x12341A00, BASE + 0x1E9980, 0x213F9890, 10, factor)) <= 0x200
        for factor in (1.10, 1.15, 1.20, 1.25):
            rate = animation_rate_shim(0x12341E00, BASE + 0x6C6C80, 0x213F9890,
                                       10, 0x22000000, 0x23000000, 0x24000000, 1.25, factor)
            instructions = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(rate, 0))
            assert sum(i.size for i in instructions) == len(rate) <= 0x200
            assert instructions[-1].mnemonic == "ret"
            assert len({i.op_str for i in instructions if i.mnemonic.startswith("j")}) == 1
            assert len([i for i in instructions if i.mnemonic == "mulss"]) == 1
            assert bytes.fromhex("41 81 7C 02 18 7A 00 00 00") in rate
        print("self-check passed")
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("pc", type=lambda s: int(s, 0))
    parser.add_argument("seconds", type=float)
    parser.add_argument("factor", type=float, choices=(1.00, 1.10, 1.15, 1.20, 1.25))
    parser.add_argument("--animation-factor", type=float, choices=(1.00, 1.10, 1.15, 1.20, 1.25), default=1.00)
    parser.add_argument("--baseline-bits", type=lambda value: int(value, 0),
                        choices=RUN_BASELINES, default=0x3E2BB98D,
                        help="Exact run parameter from a preceding vanilla capture")
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 60:
        parser.error("seconds must be finite and within 0..60")
    reader = ProcessReader(args.pid)
    try:
        if reader.read(args.pc + 0xA9E9, 1) != b"\xff" or reader.read(args.pc + 0xA9F0, 1) != b"\xfe":
            raise ValueError("Verified selector must be FF/FE before perturbation; reload verified context")
        physics_id = struct.unpack("<i", reader.read(args.pc + 0x9FCC, 4))[0]
        def build(log: int, original: int) -> bytes:
            return perturb_shim(log, original, args.pc, physics_id, args.factor, args.baseline_bits)
        owner = struct.unpack("<Q", reader.read(args.pc + 0x4C0, 8))[0]
        controller = struct.unpack("<Q", reader.read(owner + 0x108, 8))[0]
        channel = struct.unpack("<Q", reader.read(controller + 0x2F0, 8))[0]
        print(json.dumps({"requested_movement_factor": args.factor,
                          "requested_animation_factor": args.animation_factor,
                          "original_run_bits": hex(args.baseline_bits),
                          "monotonic_ns": time.monotonic_ns()}), flush=True)
        def rate_build(log: int, original: int) -> bytes:
            if args.animation_factor == 1.00:
                return rate_shim(log, original)
            return animation_rate_shim(log, original, args.pc, physics_id, owner,
                                       controller, channel, args.factor, args.animation_factor, args.baseline_bits)
        trace(reader, args.pid, args.pc, args.seconds, build, rate_build)
    finally:
        reader.close()


if __name__ == "__main__":
    main()
