"""Find COM virtual calls made through an object pointer stored at a known field.

Usage: vcall_scan.py <field_offset_hex> <vtbl_offset_hex>[,<vtbl_offset_hex>...]

Heuristic (MSVC x64 pattern):
    mov  rcx, qword ptr [<base> + <field>]    ; this = object pointer
    mov  rax, qword ptr [rcx]                 ; vtable
    call qword ptr [rax + <vtbl_offset>]
within a short window. Reports every .pdata function containing a match.
Heuristic only: a hit means "calls vtable slot X on something loaded from field F".
"""

from __future__ import annotations

import re
import sys

from xref import disasm, load_image

WINDOW = 12


def scan(field: int, slots: set[int]) -> None:
    img = load_image()
    field_re = re.compile(rf"^(\w+), qword ptr \[\w+ \+ 0x{field:x}\]$")
    for begin, end in img.funcs:
        insns = disasm(img, begin, end)
        for i, insn in enumerate(insns):
            if insn.mnemonic != "call":
                continue
            call = re.fullmatch(r"qword ptr \[(\w+) \+ 0x([0-9a-f]+)\]", insn.op_str)
            if call is None or int(call.group(2), 16) not in slots:
                continue
            vt_reg = call.group(1)
            window = insns[max(0, i - WINDOW):i]
            vt_load = next((w for w in reversed(window)
                            if w.mnemonic == "mov" and w.op_str.startswith(f"{vt_reg}, qword ptr [")
                            and w.op_str.endswith("]") and "+" not in w.op_str), None)
            if vt_load is None:
                continue
            obj_reg = vt_load.op_str.split("[", 1)[1].rstrip("]")
            obj_load = next((w for w in reversed(window)
                             if w.mnemonic == "mov" and w.address < vt_load.address
                             and (m := field_re.match(w.op_str)) and m.group(1) == obj_reg), None)
            if obj_load is not None:
                print(f"0x{insn.address:X}  slot 0x{call.group(2)}  "
                      f"func 0x{begin:X}-0x{end:X}  obj<-0x{obj_load.address:X}")


if __name__ == "__main__":
    scan(int(sys.argv[1], 16), {int(s, 16) for s in sys.argv[2].split(",")})
