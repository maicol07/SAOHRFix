"""Resolve MSVC x64 RTTI class names to vtables.

Usage: rtti.py <mangled-or-plain name> [slots]
  e.g. rtti.py CChrStatusMove 24      (plain -> ".?AVCChrStatusMove@@")
       rtti.py vt:879BD0               (reverse: vtable rva -> class name)

Chain: TypeDescriptor (name string - 0x10) <- CompleteObjectLocator (sig=1,
pTypeDescriptor rva) <- vtable[-1]. Prints every vtable (one per base subobject
offset) and its first N slots. Read-only.
"""

from __future__ import annotations

import struct
import sys

from xref import load_image


def class_of_vtable(vtable_rva: int) -> str:
    img = load_image()
    pe = img.pe
    col = struct.unpack("<Q", pe.get_data(vtable_rva - 8, 8))[0] - pe.OPTIONAL_HEADER.ImageBase
    sig, obj_off, _cd, td = struct.unpack("<IIII", pe.get_data(col, 16))
    if sig != 1:
        raise ValueError(f"no COL before vtable 0x{vtable_rva:X}")
    return f"{pe.get_data(td + 0x10, 200).split(b'\0')[0].decode()} (this-offset 0x{obj_off:X})"


def main(name: str, slots: int) -> None:
    if name.startswith("vt:"):
        print(class_of_vtable(int(name[3:], 16)))
        return
    img = load_image()
    pe = img.pe
    ib = pe.OPTIONAL_HEADER.ImageBase
    mangled = name if name.startswith(".?A") else f".?AV{name}@@"
    data_secs = [s for s in pe.sections if s.Name.rstrip(b"\0") in (b".rdata", b".data")]
    td = None
    for sec in data_secs:
        i = sec.get_data().find(mangled.encode() + b"\0")
        if i != -1:
            td = sec.VirtualAddress + i - 0x10
            break
    if td is None:
        raise KeyError(f"type descriptor not found: {mangled}")
    rdata = next(s for s in pe.sections if s.Name.startswith(b".rdata"))
    raw = rdata.get_data()
    base = rdata.VirtualAddress
    print(f"{mangled} TypeDescriptor 0x{td:X}")
    for off in range(0, len(raw) - 24, 4):
        sig, obj_off, _cd, p_td = struct.unpack_from("<IIII", raw, off)
        if sig != 1 or p_td != td:
            continue
        col = base + off
        needle = struct.pack("<Q", ib + col)
        j = raw.find(needle)
        while j != -1:
            vt = base + j + 8
            funcs = [struct.unpack_from("<Q", raw, j + 8 + k * 8)[0] - ib for k in range(slots)]
            print(f"  COL 0x{col:X} (this-offset 0x{obj_off:X}) vtable 0x{vt:X}")
            print("   " + " ".join(f"[{k:02X}]{f:X}" for k, f in enumerate(funcs) if 0x1000 <= f < 0x7FE000))
            j = raw.find(needle, j + 8)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 16)
