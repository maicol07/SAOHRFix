"""Read-only Windows process inspection for MOVEMENT-01. No attach or writes.

Usage: runtime_read.py read <pid> <VA> <size>
       runtime_read.py find-vtable <pid> <vtable-RVA>
       runtime_read.py self-check
Reads are not atomic snapshots. Scan failures are counted, never hidden.
"""

from __future__ import annotations

import argparse
import ctypes as ct
from ctypes import wintypes as wt
import hashlib
import json
from pathlib import Path
import struct

from xref import GAME_EXE

BASE = 0x140000000
SHA256 = "1923f0d8d2cad559d6ad6e001af54ea5ea5aa70171323f42d4e1fa3d63699e43"


class MemoryRegion(ct.Structure):
    _fields_ = [("base", ct.c_void_p), ("allocation", ct.c_void_p),
                ("allocation_protect", wt.DWORD), ("partition", wt.WORD),
                ("size", ct.c_size_t), ("state", wt.DWORD),
                ("protect", wt.DWORD), ("kind", wt.DWORD)]


class ProcessReader:
    def __init__(self, pid: int) -> None:
        self.api = ct.WinDLL("kernel32", use_last_error=True)
        self.api.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self.api.OpenProcess.restype = wt.HANDLE
        self.api.CloseHandle.argtypes = [wt.HANDLE]
        self.api.CloseHandle.restype = wt.BOOL
        self.api.ReadProcessMemory.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_void_p,
                                              ct.c_size_t, ct.POINTER(ct.c_size_t)]
        self.api.ReadProcessMemory.restype = wt.BOOL
        self.api.VirtualQueryEx.argtypes = [wt.HANDLE, ct.c_void_p,
                                            ct.POINTER(MemoryRegion), ct.c_size_t]
        self.api.VirtualQueryEx.restype = ct.c_size_t
        self.api.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD,
                                                       wt.LPWSTR, ct.POINTER(wt.DWORD)]
        self.api.QueryFullProcessImageNameW.restype = wt.BOOL
        self.handle = self.api.OpenProcess(0x410, False, pid)
        if not self.handle:
            raise ct.WinError(ct.get_last_error())
        try:
            path = ct.create_unicode_buffer(32768)
            size = wt.DWORD(len(path))
            if not self.api.QueryFullProcessImageNameW(self.handle, 0, path, ct.byref(size)):
                raise ct.WinError(ct.get_last_error())
            if Path(path.value).resolve() != GAME_EXE.resolve():
                raise ValueError(f"PID {pid} is not {GAME_EXE}: {path.value}")
            if hashlib.sha256(GAME_EXE.read_bytes()).hexdigest() != SHA256:
                raise ValueError("Unsupported executable SHA-256")
            if self.read(BASE, 2) != b"MZ":
                raise ValueError("Expected PE image at 0x140000000")
        except (OSError, ValueError):
            self.close()
            raise

    def close(self) -> None:
        if not self.api.CloseHandle(self.handle):
            raise ct.WinError(ct.get_last_error())

    def read(self, address: int, size: int) -> bytes:
        buffer = ct.create_string_buffer(size)
        count = ct.c_size_t()
        if not self.api.ReadProcessMemory(self.handle, address, buffer, size, ct.byref(count)):
            raise OSError(ct.get_last_error(), f"ReadProcessMemory VA=0x{address:X} size={size}")
        if count.value != size:
            raise OSError(f"Short read VA=0x{address:X}: {count.value}/{size}")
        return buffer.raw

    def find_vtable(self, rva: int) -> list[int]:
        needle = struct.pack("<Q", BASE + rva)
        address = 0
        hits: list[int] = []
        failed = 0
        region = MemoryRegion()
        while self.api.VirtualQueryEx(self.handle, address, ct.byref(region), ct.sizeof(region)):
            start = region.base or 0
            end = start + region.size
            if end <= address:
                raise ValueError("Non-progressing VirtualQueryEx region")
            if region.state == 0x1000 and region.kind == 0x20000 and region.protect in (4, 8, 0x40, 0x80):
                for offset in range(start, end, 0x100000):
                    try:
                        data = self.read(offset, min(0x100000, end - offset))
                    except OSError:
                        failed += 1
                        continue
                    hits.extend(offset + i for i in aligned_matches(data, needle))
            address = end
        print(json.dumps({"unreadable_chunks": failed, "scan": "private writable, 8-byte aligned"}))
        return hits


def aligned_matches(data: bytes, needle: bytes) -> list[int]:
    hits: list[int] = []
    offset = data.find(needle)
    while offset >= 0:
        if offset % 8 == 0:
            hits.append(offset)
        offset = data.find(needle, offset + 1)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("read", "find-vtable", "self-check"))
    parser.add_argument("pid", type=int, nargs="?")
    parser.add_argument("address", type=lambda s: int(s, 0), nargs="?")
    parser.add_argument("size", type=lambda s: int(s, 0), nargs="?")
    args = parser.parse_args()
    if args.command == "self-check":
        needle = struct.pack("<Q", BASE + 0x80AE08)
        assert aligned_matches(needle + b"x" + needle + b"\0" * 7 + needle, needle) == [0, 24]
        assert ct.sizeof(MemoryRegion) == 48
        print("self-check passed")
        return
    if args.pid is None or args.address is None or args.pid <= 0 or args.address < 0:
        parser.error("positive PID and nonnegative address required")
    if args.command == "read" and (args.size is None or not 0 < args.size <= 0x100000):
        parser.error("read size must be 1..0x100000")
    reader = ProcessReader(args.pid)
    try:
        if args.command == "read":
            print(reader.read(args.address, args.size).hex(" "))
        else:
            print(json.dumps([f"0x{p:X}" for p in reader.find_vtable(args.address)]))
    finally:
        reader.close()


if __name__ == "__main__":
    main()
