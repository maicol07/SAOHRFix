"""Static PE reconnaissance for SAOHRFix Phase 0.

Dumps headers, sections and the full import table of a PE image.
Read-only: never writes to the target.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sys
from pathlib import Path

import pefile

CATEGORIES: dict[str, tuple[str, ...]] = {
    "graphics": ("d3d", "dxgi", "d3dcompiler", "opengl", "vulkan", "nvapi"),
    "audio": ("xaudio", "x3daudio", "dsound", "mmdevapi", "audioses", "avrt", "winmm", "ole32"),
    "input": ("xinput", "dinput", "hid", "user32"),
    "file_io": ("kernel32", "shlwapi", "shell32"),
    "platform": ("steam_api", "msvcp", "vcruntime", "api-ms", "ucrtbase", "advapi32"),
}


def categorize(dll: str) -> str:
    low = dll.lower()
    for name, prefixes in CATEGORIES.items():
        if any(p in low for p in prefixes):
            return name
    return "other"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(target: Path) -> None:
    pe = pefile.PE(str(target), fast_load=False)
    oh = pe.OPTIONAL_HEADER
    fh = pe.FILE_HEADER

    print(f"file            {target}")
    print(f"size            {target.stat().st_size}")
    print(f"sha256          {sha256(target)}")
    print(f"machine         0x{fh.Machine:04X}")
    print(f"pe_timestamp    {fh.TimeDateStamp} "
          f"({dt.datetime.fromtimestamp(fh.TimeDateStamp, dt.UTC).isoformat()})")
    print(f"image_base      0x{oh.ImageBase:X}")
    print(f"entry_point_rva 0x{oh.AddressOfEntryPoint:X}")
    print(f"size_of_image   0x{oh.SizeOfImage:X}")
    print(f"subsystem       {oh.Subsystem}")
    print(f"dll_chars       0x{oh.DllCharacteristics:04X}")
    print(f"linker          {oh.MajorLinkerVersion}.{oh.MinorLinkerVersion}")
    print(f"checksum        0x{oh.CheckSum:X}")

    print("\n[sections]")
    for section in pe.sections:
        name = section.Name.rstrip(b"\x00").decode("ascii", "replace")
        print(f"  {name:<8} rva=0x{section.VirtualAddress:08X} "
              f"vsize=0x{section.Misc_VirtualSize:08X} "
              f"raw=0x{section.SizeOfRawData:08X} chars=0x{section.Characteristics:08X}")

    print("\n[imports]")
    for entry in sorted(pe.DIRECTORY_ENTRY_IMPORT, key=lambda e: e.dll.lower()):
        dll = entry.dll.decode()
        funcs = [imp.name.decode() if imp.name else f"#{imp.ordinal}" for imp in entry.imports]
        print(f"  {dll}  [{categorize(dll)}]  ({len(funcs)})")
        for func in funcs:
            print(f"      {func}")

    if hasattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT"):
        print("\n[delay_imports]")
        for entry in pe.DIRECTORY_ENTRY_DELAY_IMPORT:
            dll = entry.dll.decode()
            funcs = [imp.name.decode() if imp.name else f"#{imp.ordinal}" for imp in entry.imports]
            print(f"  {dll}  [{categorize(dll)}]  ({len(funcs)})")
            for func in funcs:
                print(f"      {func}")

    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        print("\n[exports]")
        for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            print(f"  {exp.name.decode() if exp.name else exp.ordinal} rva=0x{exp.address:X}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
