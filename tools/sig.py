"""Generate and verify AOB signatures for sao_hr.exe functions.

Usage: sig.py <rva> [<rva> ...]

For each RVA: takes instructions from the start until the pattern is unique
in .text (max 64 bytes), wildcarding RIP-relative displacements and rel32
branch targets. Prints "<rva> <unique|NOT-UNIQUE> <pattern>".
"""

from __future__ import annotations

import re
import sys

import capstone

from xref import load_image

MAX_LEN = 64


def pattern_for(code: bytes, rva: int) -> list[int | None]:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    out: list[int | None] = []
    for insn in md.disasm(code, rva):
        raw: list[int | None] = list(insn.bytes)
        enc = insn.disp_offset if "rip" in insn.op_str else 0
        if enc:
            raw[enc:enc + 4] = [None] * 4
        if insn.mnemonic in ("call", "jmp") and insn.bytes[0] in (0xE8, 0xE9):
            raw[1:5] = [None] * 4
        out.extend(raw)
        if len(out) >= MAX_LEN:
            break
    return out[:MAX_LEN]


def to_regex(pat: list[int | None]) -> re.Pattern[bytes]:
    return re.compile(b"".join(b"." if b is None else re.escape(bytes([b])) for b in pat), re.S)


def fmt(pat: list[int | None]) -> str:
    return " ".join("??" if b is None else f"{b:02X}" for b in pat)


def main(rvas: list[int]) -> None:
    img = load_image()
    text = img.pe.sections[0]
    data = text.get_data()
    for rva in rvas:
        full = pattern_for(img.pe.get_data(rva, MAX_LEN + 16), rva)
        for n in range(8, len(full) + 1):
            hits = [m.start() for m in to_regex(full[:n]).finditer(data)]
            if len(hits) == 1:
                ok = hits[0] + text.VirtualAddress == rva
                print(f"0x{rva:X} {'unique' if ok else 'WRONG-HIT'} {fmt(full[:n])}")
                break
        else:
            print(f"0x{rva:X} NOT-UNIQUE {fmt(full)}")


if __name__ == "__main__":
    main([int(a, 16) for a in sys.argv[1:]])
