"""Extract ASCII/UTF-16 strings from a PE image with their RVA.

Read-only. Output format: "<rva-hex>\t<encoding>\t<string>".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pefile

ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")


def main(target: Path, out: Path) -> None:
    pe = pefile.PE(str(target), fast_load=True)
    with out.open("w", encoding="utf-8", errors="replace") as handle:
        for section in pe.sections:
            data = section.get_data()
            base = section.VirtualAddress
            name = section.Name.rstrip(b"\x00").decode("ascii", "replace")
            for match in ASCII_RE.finditer(data):
                handle.write(f"0x{base + match.start():08X}\t{name}\ta\t"
                             f"{match.group().decode('ascii')}\n")
            for match in UTF16_RE.finditer(data):
                handle.write(f"0x{base + match.start():08X}\t{name}\tw\t"
                             f"{match.group().decode('utf-16-le')}\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
