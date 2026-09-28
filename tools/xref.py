"""Static xref helper for sao_hr.exe (Phase 0).

Subcommands:
  index                 disassemble every .pdata range, cache RIP-relative refs
                        and direct call/jmp targets (import thunks sit outside .pdata)
  imp  <DLL!Func>       callers of an import (IAT slot refs)
  refs <rva>            instructions referencing <rva> (RIP-relative)
  func <rva>            .pdata range containing <rva>
  dis  <rva> [max]      annotated disassembly of the .pdata range containing <rva>

Read-only. Cache lives next to this script in ../.cache/ (git-ignored).
"""

from __future__ import annotations

import bisect
import pickle
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import capstone
import pefile

GAME_EXE = Path(r"W:\SteamLibrary\steamapps\common\SAOHR\sao_hr.exe")
CACHE = Path(__file__).resolve().parent.parent / ".cache" / "xref.pkl"
RIP_RE = re.compile(r"\[rip ([+-]) 0x([0-9a-f]+)\]")


@dataclass(frozen=True)
class Image:
    pe: pefile.PE
    funcs: list[tuple[int, int]]  # sorted (begin_rva, end_rva) from .pdata
    imports: dict[int, str]  # IAT slot rva -> "dll!name"


def load_image() -> Image:
    pe = pefile.PE(str(GAME_EXE), fast_load=False)
    funcs = sorted({(e.struct.BeginAddress, e.struct.EndAddress)
                    for e in pe.DIRECTORY_ENTRY_EXCEPTION})
    imports = {
        imp.address - pe.OPTIONAL_HEADER.ImageBase:
            f"{entry.dll.decode()}!{imp.name.decode() if imp.name else imp.ordinal}"
        for entry in pe.DIRECTORY_ENTRY_IMPORT for imp in entry.imports
    }
    return Image(pe, funcs, imports)


def rip_target(insn: capstone.CsInsn) -> int | None:
    match = RIP_RE.search(insn.op_str)
    if match is None:
        return None
    disp = int(match.group(2), 16)
    return insn.address + insn.size + (disp if match.group(1) == "+" else -disp)


def disasm(img: Image, begin: int, end: int) -> list[capstone.CsInsn]:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    code = img.pe.get_data(begin, end - begin)
    return list(md.disasm(code, begin))


def build_index(img: Image) -> dict[int, list[int]]:
    refs: dict[int, list[int]] = {}
    for begin, end in img.funcs:
        for insn in disasm(img, begin, end):
            target = rip_target(insn)
            if target is None and insn.mnemonic in ("call", "jmp") and insn.op_str.startswith("0x"):
                target = int(insn.op_str, 16)
            if target is not None:
                refs.setdefault(target, []).append(insn.address)
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_bytes(pickle.dumps(refs))
    return refs


def load_index() -> dict[int, list[int]]:
    if not CACHE.exists():
        raise FileNotFoundError(f"xref cache missing: run 'index' first ({CACHE})")
    return pickle.loads(CACHE.read_bytes())


def func_of(img: Image, rva: int) -> tuple[int, int] | None:
    i = bisect.bisect_right(img.funcs, (rva, 0xFFFFFFFF)) - 1
    if i >= 0 and img.funcs[i][0] <= rva < img.funcs[i][1]:
        return img.funcs[i]
    return None


def read_cstr(img: Image, rva: int) -> str | None:
    try:
        raw = img.pe.get_data(rva, 160)
    except pefile.PEFormatError:
        return None
    text = raw.split(b"\x00", 1)[0]
    if len(text) >= 4 and all(0x20 <= b < 0x7F for b in text):
        return text.decode("ascii")
    wide = raw.split(b"\x00\x00", 1)[0]
    if len(wide) >= 8 and wide[1::2].count(0) == len(wide[1::2]):
        return "L" + wide[::2].decode("ascii", "replace")
    return None


def print_refs(img: Image, sources: list[int]) -> None:
    for src in sorted(sources):
        fn = func_of(img, src)
        fn_txt = f"func 0x{fn[0]:X}-0x{fn[1]:X}" if fn else "func ?"
        print(f"  0x{src:X}  ({fn_txt})")


def cmd_dis(img: Image, rva: int, limit: int) -> None:
    fn = func_of(img, rva)
    if fn is None:
        # ponytail: leaf funcs have no .pdata; dump a fixed window, reader stops at first ret
        fn = (rva, rva + 0x100)
        print(f"; leaf/no .pdata at 0x{rva:X}, raw 0x100 bytes")
    else:
        print(f"; func 0x{fn[0]:X}-0x{fn[1]:X} size 0x{fn[1] - fn[0]:X}")
    for insn in disasm(img, fn[0], fn[1])[:limit]:
        note = ""
        target = rip_target(insn)
        if target is not None:
            if target in img.imports:
                note = f"  ; {img.imports[target]}"
            elif (text := read_cstr(img, target)) is not None:
                note = f"  ; \"{text[:70]}\""
            else:
                note = f"  ; ->0x{target:X}"
        elif insn.mnemonic == "call" and insn.op_str.startswith("0x"):
            note = f"  ; sub_{int(insn.op_str, 16):X}"
        print(f"{insn.address:08X}  {insn.mnemonic:<6} {insn.op_str}{note}")


def main(argv: list[str]) -> None:
    img = load_image()
    cmd = argv[0]
    if cmd == "index":
        refs = build_index(img)
        print(f"indexed {len(img.funcs)} funcs, {sum(map(len, refs.values()))} rip refs")
    elif cmd == "imp":
        slots = [rva for rva, name in img.imports.items() if name.lower() == argv[1].lower()]
        if not slots:
            raise KeyError(f"import not found: {argv[1]}")
        print(f"{argv[1]} IAT slot 0x{slots[0]:X}")
        print_refs(img, load_index().get(slots[0], []))
    elif cmd == "refs":
        print_refs(img, load_index().get(int(argv[1], 16), []))
    elif cmd == "func":
        fn = func_of(img, int(argv[1], 16))
        print(f"0x{fn[0]:X}-0x{fn[1]:X}" if fn else "none")
    elif cmd == "dis":
        cmd_dis(img, int(argv[1], 16), int(argv[2]) if len(argv) > 2 else 400)
    else:
        raise ValueError(f"unknown command: {cmd}")


if __name__ == "__main__":
    main(sys.argv[1:])
