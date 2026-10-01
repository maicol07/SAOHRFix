"""Temporary player-only run parameter perturbation at the verified setter.

Usage: run_perturb.py PID CChrPc-VA seconds factor
Only factors 1.10/1.25, only observed exploration run branch and caller pair.
Instance vptrs restored by walk_trace; no permanent game patch or global write.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys

from runtime_read import BASE, ProcessReader
from walk_trace import producer_shim, trace


def perturb_shim(log: int, original: int, pc: int, physics_id: int, factor: float) -> bytes:
    if factor not in (1.10, 1.25):
        raise ValueError("Only 1.10/1.25 diagnostic perturbations allowed")
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
    require_equal(bytes.fromhex("66 0F 7E D0 3D") + struct.pack("<f", 0.1677))
    code.extend(bytes.fromhex("B8") + struct.pack("<f", factor))
    code.extend(bytes.fromhex("50 F3 0F 59 14 24 58"))  # multiply incoming xmm2 only
    restore = len(code)
    code.extend(bytes.fromhex("41 5A 58 9D"))
    for displacement in jumps:
        struct.pack_into("<i", code, displacement, restore - displacement - 4)
    code.extend(producer_shim(log, original))
    return bytes(code)


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
        print("self-check passed")
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("pc", type=lambda s: int(s, 0))
    parser.add_argument("seconds", type=float)
    parser.add_argument("factor", type=float, choices=(1.10, 1.25))
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 60:
        parser.error("seconds must be finite and within 0..60")
    reader = ProcessReader(args.pid)
    try:
        physics_id = struct.unpack("<i", reader.read(args.pc + 0x9FCC, 4))[0]
        def build(log: int, original: int) -> bytes:
            return perturb_shim(log, original, args.pc, physics_id, args.factor)
        trace(reader, args.pid, args.pc, args.seconds, build)
    finally:
        reader.close()


if __name__ == "__main__":
    main()
