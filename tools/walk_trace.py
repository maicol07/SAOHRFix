"""Reversible player, KCC and animation-channel logging shims.

Usage: walk_trace.py PID CChrPc-VA seconds
Copies three instance vtables, logs entries, calls the originals.
Restores all instance vptrs in finally. The private 12 KiB page stays until game exit:
freeing executable memory while a thread may still return through it is unsafe.
This is diagnostic instrumentation, not an unmodified vanilla capture.
"""

from __future__ import annotations

import argparse
import ctypes as ct
from ctypes import wintypes as wt
import json
import math
import struct
import statistics
import sys
import time
from collections import Counter
from collections.abc import Callable

from movement_probe import resolve
from runtime_read import BASE, ProcessReader


def suspect_vertical(delta_y: float, y: float, start_y: float) -> bool:
    # Poll deltas can span several updates; this flags observations, not tunneling.
    return abs(delta_y) > 0.5 or abs(y - start_y) > 2.0


def active_clip(reader: ProcessReader, channel: int) -> int:
    array = struct.unpack("<Q", reader.read(channel + 0xA8, 8))[0]
    count = struct.unpack("<i", reader.read(channel + 0xB8, 4))[0]
    index = struct.unpack("<i", reader.read(channel + 0x114, 4))[0]
    if not array or not 0 <= index < count:
        return -1
    return struct.unpack("<i", reader.read(array + index * 40 + 0x18, 4))[0]


def producer_shim(log: int, original: int) -> bytes:
    # At 1E993F reached from 206660, R12D is x*x and R15D is x*x+y*y.
    # These are gameplay-consumed magnitudes; signed axes are already lost.
    code = bytearray.fromhex("9C 50 41 52 41 53 49 BA") + struct.pack("<Q", log)
    code += bytes.fromhex("49 FF 02")
    for source, destination in (("48 8B 44 24 20", 8),
                                ("65 48 8B 04 25 48 00 00 00", 16),
                                ("48 89 C8", 24), ("44 89 E0", 32),
                                ("44 89 F8", 40), ("66 0F 7E D0", 48),
                                ("48 8B 84 24 B0 00 00 00", 56)):
        code += bytes.fromhex(source + " 49 89 42") + bytes([destination])
    for source, destination in (("0F B6 81 A6 F8 00 00", 64),
                                ("0F B6 81 AD F8 00 00", 72),
                                ("0F B6 81 E9 A9 00 00", 80),
                                ("0F B6 81 F0 A9 00 00", 88)):
        code += bytes.fromhex(source + " 49 89 42") + bytes([destination])
    code += bytes.fromhex("49 FF 02 41 5B 41 5A 58 9D FF 25 00 00 00 00")
    code += struct.pack("<Q", original)
    return bytes(code)


def special_shim(log: int, original: int) -> bytes:
    # TRACE-246-01: only the setter return 1F625A, after the original branch tests.
    # 1F5B30 pushes 3 registers and reserves 150h; parent return is entry RSP+170h.
    code = bytearray.fromhex("9C 50 41 52 49 BA") + struct.pack("<Q", BASE + 0x1F625A)
    code += bytes.fromhex("4C 39 54 24 18 0F 85 00 00 00 00")
    reject = len(code) - 4
    code += bytes.fromhex("49 BA") + struct.pack("<Q", log)
    code += bytes.fromhex("49 FF 02")
    for source, destination in (("48 8B 84 24 88 01 00 00", 8),
                                ("48 89 C8", 16), ("0F B6 81 25 A0 00 00", 24),
                                ("8B 81 DC 9F 00 00", 32), ("8B 81 F8 9F 00 00", 40),
                                ("8B 81 58 9F 00 00", 48), ("66 0F 7E D0", 56),
                                ("66 44 0F 7E D8", 64), ("8B 44 24 70", 72),
                                ("48 8B 45 80", 80), ("48 8B 45 88", 88),
                                ("48 8B 81 10 9E 00 00", 96),
                                ("48 8B 81 18 9E 00 00", 104)):
        code += bytes.fromhex(source + " 49 89 42") + bytes([destination])
    code += bytes.fromhex("49 FF 02")
    struct.pack_into("<i", code, reject, len(code) - reject - 4)
    code += bytes.fromhex("41 5A 58 9D FF 25 00 00 00 00") + struct.pack("<Q", original)
    return bytes(code)


def animation_shim(log: int, original: int) -> bytes:
    code = bytearray.fromhex("9C 50 41 52 41 53 49 BA") + struct.pack("<Q", log)
    code += bytes.fromhex("49 FF 02")
    for source, destination in (("48 8B 44 24 20", 8),
                                ("65 48 8B 04 25 48 00 00 00", 16),
                                ("48 89 C8", 24), ("89 D0", 32),
                                ("44 89 C0", 40), ("44 89 C8", 48),
                                ("8B 44 24 48", 56),
                                ("0F B6 81 A6 F8 00 00", 64)):
        code += bytes.fromhex(source + " 49 89 42") + bytes([destination])
    code += bytes.fromhex("49 FF 02 41 5B 41 5A 58 9D FF 25 00 00 00 00")
    code += struct.pack("<Q", original)
    return bytes(code)


def rate_shim(log: int, original: int) -> bytes:
    # Original getter only computes xmm0 = global factor * channel+1E8.
    # Invoke it with aligned shadow space, log its actual return, return unchanged.
    code = bytearray.fromhex("9C 50 41 52 41 53 49 BA") + struct.pack("<Q", log)
    code += bytes.fromhex("49 FF 02")
    for source, destination in (("48 8B 44 24 20", 8),
                                ("65 48 8B 04 25 48 00 00 00", 16),
                                ("48 89 C8", 24),
                                ("8B 81 E8 01 00 00", 40)):
        code += bytes.fromhex(source + " 49 89 42") + bytes([destination])
    code += bytes.fromhex("48 83 EC 28 48 B8") + struct.pack("<Q", original)
    code += bytes.fromhex("FF D0 48 83 C4 28 66 0F 7E C0 49 BA") + struct.pack("<Q", log)
    code += bytes.fromhex("49 89 42 20 49 FF 02 41 5B 41 5A 58 9D C3")
    return bytes(code)


def shim(log: int, original: int, pc: int, production: int, animation: int) -> bytes:
    # Save flags and scratch registers. Entry RSP is now RSP+32.
    code = bytearray.fromhex("9C 50 41 52 41 53 49 BA") + struct.pack("<Q", log)
    code += bytes.fromhex("49 FF 02")  # odd sequence marks an incomplete record

    def store_rax(destination: int) -> bytes:
        return (bytes.fromhex("49 89 42") + bytes([destination]) if destination < 128 else
                bytes.fromhex("49 89 82") + struct.pack("<i", destination))

    for source, destination in (("48 8B 44 24 20", 8),
                                ("65 48 8B 04 25 48 00 00 00", 16),
                                ("48 89 C8", 24),
                                ("48 8B 02", 32), ("48 8B 42 08", 40)):
        code += bytes.fromhex(source) + store_rax(destination)
    for address, destination in ((pc + 0x9F20, 48), (pc + 0xA9E8, 56),
                                 (pc + 0xF8A6, 64), (pc + 0xF8AD, 72),
                                 (BASE + 0xA63238, 80),
                                 (BASE + 0xA63240, 136), (pc + 0xA9F0, 152)):
        code += bytes.fromhex("48 B8") + struct.pack("<Q", address)
        code += bytes.fromhex("48 8B 00") + store_rax(destination)
    # Verified 58CF40 prologue: push rbp, sub rsp,E0; its return is entry RSP+F0.
    for source, destination in (("48 8B 84 24 10 01 00 00", 88),
                                ("66 0F 7E F0", 96), ("48 89 D8", 104),
                                ("48 8B 43 40", 112), ("48 8B 43 48", 120),
                                ("48 8B 83 F4 00 00 00", 128)):
        code += bytes.fromhex(source) + store_rax(destination)
    code += bytes.fromhex("48 8B 84 24 60 01 00 00") + store_rax(160)
    code += bytes.fromhex("48 B8") + struct.pack("<Q", BASE + 0xC69068)
    code += bytes.fromhex("8B 00 83 E8 01 83 E0 3F 48 69 C0 8C 00 00 00 49 BB")
    code += struct.pack("<Q", BASE + 0xC66D60 + 0x80)
    code += bytes.fromhex("4C 01 D8 8B 00") + store_rax(144)
    code += bytes.fromhex("49 BB") + struct.pack("<Q", production)
    for source, destination in ((0, 168), (8, 176), (16, 184), (24, 192),
                                (32, 200), (40, 208), (48, 216), (56, 224),
                                (64, 232), (72, 240), (80, 248), (88, 256), (0, 264)):
        code += bytes.fromhex("49 8B 43") + bytes([source]) + store_rax(destination)
    code += bytes.fromhex("49 BB") + struct.pack("<Q", animation)
    for source, destination in ((0, 272), (8, 280), (16, 288), (24, 296),
                                (32, 304), (40, 312), (48, 320), (56, 328),
                                (64, 336), (0, 344)):
        code += bytes.fromhex("49 8B 43") + bytes([source]) + store_rax(destination)
    code += bytes.fromhex("49 FF 02 41 5B 41 5A 58 9D FF 25 00 00 00 00")
    code += struct.pack("<Q", original)
    return bytes(code)


def trace(reader: ProcessReader, pid: int, pc: int, seconds: float,
          production_builder: Callable[[int, int], bytes],
          rate_builder: Callable[[int, int], bytes]) -> None:
    identity = resolve(reader, pc)
    _, wrapper, kcc = identity
    ghost = struct.unpack("<Q", reader.read(kcc + 0x10, 8))[0]
    if struct.unpack("<Q", reader.read(ghost, 8))[0] != BASE + 0x8C3F08:
        raise ValueError("Unexpected player Bullet ghost")
    original_vptr = BASE + 0x879BD0
    original = struct.unpack("<Q", reader.read(original_vptr + 0x18, 8))[0]
    if original != BASE + 0x72A5F0:
        raise ValueError("Unexpected setWalkDirection implementation")
    pc_vptr = BASE + 0x80AE08
    if struct.unpack("<Q", reader.read(pc, 8))[0] != pc_vptr:
        raise ValueError("Player vptr is already modified")
    setter = struct.unpack("<Q", reader.read(pc_vptr + 0x3E8, 8))[0]
    if setter != BASE + 0x1E9980:
        raise ValueError("Unexpected player movement setter")
    animation_target = struct.unpack("<Q", reader.read(pc_vptr + 0x460, 8))[0]
    if animation_target != BASE + 0x1DDC10:
        raise ValueError("Unexpected player animation request method")
    mode = struct.unpack("<i", reader.read(BASE + 0xC69060, 4))[0]
    if mode != 64:
        raise ValueError("Trace requires the verified 64-entry input history mode")
    owner = struct.unpack("<Q", reader.read(pc + 0x4C0, 8))[0]
    controller = struct.unpack("<Q", reader.read(owner + 0x108, 8))[0]
    channel = struct.unpack("<Q", reader.read(controller + 0x2F0, 8))[0]
    channel_vptr = BASE + 0x822AE8
    if struct.unpack("<Q", reader.read(channel, 8))[0] != channel_vptr:
        raise ValueError("Unexpected player animation channel vptr")
    rate_target = struct.unpack("<Q", reader.read(channel_vptr + 0x30, 8))[0]
    if rate_target != BASE + 0x6C6C80:
        raise ValueError("Unexpected channel rate getter")
    api = reader.api
    api.VirtualAllocEx.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_size_t, wt.DWORD, wt.DWORD]
    api.VirtualAllocEx.restype = ct.c_void_p
    api.WriteProcessMemory.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.POINTER(ct.c_size_t)]
    api.WriteProcessMemory.restype = wt.BOOL
    api.FlushInstructionCache.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_size_t]
    api.FlushInstructionCache.restype = wt.BOOL
    handle = api.OpenProcess(0x438, False, pid)
    if not handle:
        raise ct.WinError(ct.get_last_error())
    page = api.VirtualAllocEx(handle, None, 12288, 0x3000, 0x40)
    if not page:
        api.CloseHandle(handle)
        raise ct.WinError(ct.get_last_error())

    def write(address: int, data: bytes) -> None:
        count = ct.c_size_t()
        buffer = ct.create_string_buffer(data)
        if not api.WriteProcessMemory(handle, address, buffer, len(data), ct.byref(count)) or count.value != len(data):
            raise OSError(ct.get_last_error(), f"WriteProcessMemory VA={address:#x} size={len(data)}")

    table, entry, log = page + 8, page + 0x1000, page + 0x1800
    pc_table, producer_entry, production = page + 0x308, page + 0x1400, page + 0x1A00
    animation_entry, animation = page + 0x1600, page + 0x1B00
    channel_table, rate_entry, rate_log = page + 0xD08, page + 0x1C00, page + 0x1E00
    special_entry, special_log = page + 0x2000, page + 0x2400
    special_events: list[dict[str, object]] = []
    previous_special = 0
    rate_events: Counter[tuple[int, int, float, float]] = Counter()
    calls: dict[int, int] = {}
    records: list[dict[str, object]] = []
    previous = 0
    try:
        vtable = bytearray(reader.read(original_vptr - 8, 0x108))
        struct.pack_into("<Q", vtable, 8 + 0x18, entry)
        write(page, bytes(vtable))
        pc_copy = bytearray(reader.read(pc_vptr - 8, 0x998))
        struct.pack_into("<Q", pc_copy, 8 + 0x3E8, producer_entry)
        struct.pack_into("<Q", pc_copy, 8 + 0x460, animation_entry)
        write(page + 0x300, bytes(pc_copy))
        channel_copy = bytearray(reader.read(channel_vptr - 8, 0x1F0))
        struct.pack_into("<Q", channel_copy, 8 + 0x30, rate_entry)
        write(page + 0xD00, bytes(channel_copy))
        rate_code = rate_builder(rate_log, rate_target)
        if len(rate_code) > 0x200:
            raise ValueError("Rate diagnostic exceeds its code slot")
        write(rate_entry, rate_code)
        write(rate_log + 0x100, b"\x01")
        write(special_entry, special_shim(special_log, setter))
        production_code = production_builder(production, special_entry)
        if len(production_code) > 0x200:
            raise ValueError("Production shim exceeds its private code slot")
        write(producer_entry, production_code)
        write(animation_entry, animation_shim(animation, animation_target))
        code = shim(log, original, pc, production, animation)
        write(entry, code)
        if not api.FlushInstructionCache(handle, page, 12288):
            raise ct.WinError(ct.get_last_error())
        if resolve(reader, pc) != identity:
            raise ValueError("Player identity changed before installation")
        write(kcc, struct.pack("<Q", table))
        write(pc, struct.pack("<Q", pc_table))
        write(channel, struct.pack("<Q", channel_table))
        start = time.monotonic()
        print(json.dumps({"status": "logging", "kcc": hex(kcc), "seconds": seconds,
                          "monotonic_start_s": start}), flush=True)
        while time.monotonic() - start < seconds:
            if (struct.unpack("<i", reader.read(pc + 0x9FCC, 4))[0] != identity[0]
                    or struct.unpack("<Q", reader.read(pc + 0x4C0, 8))[0] != owner
                    or struct.unpack("<Q", reader.read(owner + 0x108, 8))[0] != controller
                    or struct.unpack("<Q", reader.read(controller + 0x2F0, 8))[0] != channel):
                raise ValueError("Player/channel relationship changed; discard capture")
            record = reader.read(log, 352)
            sequence, caller, thread, instance = struct.unpack_from("<4Q", record)
            check = struct.unpack("<Q", reader.read(log, 8))[0]
            if sequence and not sequence % 2 and sequence == check and sequence != previous:
                if instance != kcc:
                    raise ValueError("Shim logged another KCC instance")
                if struct.unpack_from("<Q", record, 104)[0] != wrapper or caller != BASE + 0x58D31F:
                    raise ValueError("Unexpected wrapper/caller: fixed stack interpretation is invalid")
                calls[caller - BASE] = calls.get(caller - BASE, 0) + 1
                vec = struct.unpack_from("<4f", record, 32)
                base, speed = struct.unpack_from("<2f", record, 48)
                dt, reciprocal = struct.unpack_from("<2f", record, 80)
                outer = struct.unpack_from("<Q", record, 88)[0]
                records.append({"t": time.monotonic() - start, "sequence": sequence,
                                "caller_rva": hex(caller - BASE), "thread": thread,
                                "vec": vec, "base": base, "speed": speed,
                                "F8A6": record[64], "F8AD": record[72],
                                "selector_state": list(record[56:64]),
                                "dt": dt, "reciprocal": reciprocal,
                                "world": struct.unpack("<4f", reader.read(ghost + 0x40, 16)),
                                "player_world": struct.unpack("<4f", reader.read(pc + 0x9DE0, 16)),
                                "target_world": struct.unpack("<4f", reader.read(pc + 0x9E20, 16)),
                                "requested_world": struct.unpack("<4f", reader.read(pc + 0x9E10, 16)),
                                "field_A025": reader.read(pc + 0xA025, 1)[0],
                                "field_A021": reader.read(pc + 0xA021, 1)[0],
                                "field_A01E": reader.read(pc + 0xA01E, 1)[0],
                                "field_A04C": reader.read(pc + 0xA04C, 1)[0],
                                "field_A03C": reader.read(pc + 0xA03C, 1)[0],
                                "field_9FDC": struct.unpack("<f", reader.read(pc + 0x9FDC, 4))[0],
                                "field_9FF8": struct.unpack("<f", reader.read(pc + 0x9FF8, 4))[0],
                                "field_9F58": struct.unpack("<f", reader.read(pc + 0x9F58, 4))[0],
                                "kcc_ground_fields": struct.unpack("<2f", reader.read(kcc + 0x20, 8)),
                                "kcc_step_fields": struct.unpack("<3f", reader.read(kcc + 0x40, 12)),
                                "kcc_contact_flags": list(reader.read(kcc + 0xE0, 4)),
                                "channel_rate": struct.unpack("<f", reader.read(channel + 0x1E8, 4))[0],
                                "downstream_rate": struct.unpack("<f", reader.read(channel + 0x1D0, 4))[0],
                                "animation_phase": struct.unpack("<f", reader.read(channel + 0x1D4, 4))[0],
                                "active_clip_id": active_clip(reader, channel),
                                "wrapper_caller_rva": hex(outer - BASE),
                                "wrapper_dt": struct.unpack_from("<f", record, 96)[0],
                                "wrapper": hex(struct.unpack_from("<Q", record, 104)[0]),
                                "pre": struct.unpack_from("<4f", record, 112),
                                "wrapper_scale": struct.unpack_from("<f", record, 128)[0],
                                "step": struct.unpack_from("<f", record, 136)[0],
                                "ring_latest_axes": struct.unpack_from("<2h", record, 144),
                                "selector_pending": record[152],
                                "manager_caller_rva": hex(struct.unpack_from("<Q", record, 160)[0] - BASE),
                                "production_sequence": struct.unpack_from("<Q", record, 168)[0],
                                "production_caller_rva": hex(struct.unpack_from("<Q", record, 176)[0] - BASE),
                                "production_thread": struct.unpack_from("<Q", record, 184)[0],
                                "production_instance": hex(struct.unpack_from("<Q", record, 192)[0]),
                                "production_x_register": struct.unpack_from("<I", record, 200)[0],
                                "production_magnitude_register": struct.unpack_from("<I", record, 208)[0],
                                "production_speed": struct.unpack_from("<f", record, 216)[0],
                                "production_outer_rva": (hex(struct.unpack_from("<Q", record, 224)[0] - BASE)
                                                         if struct.unpack_from("<Q", record, 176)[0] == BASE + 0x1E993F
                                                         else None),
                                "production_F8A6": record[232], "production_F8AD": record[240],
                                "production_selector_state": record[248],
                                "production_selector_pending": record[256],
                                "production_copy_stable": bool(struct.unpack_from("<Q", record, 168)[0])
                                and struct.unpack_from("<Q", record, 168)[0] == struct.unpack_from("<Q", record, 264)[0]
                                and not struct.unpack_from("<Q", record, 168)[0] % 2,
                                "animation_sequence": struct.unpack_from("<Q", record, 272)[0],
                                "animation_caller_rva": hex(struct.unpack_from("<Q", record, 280)[0] - BASE),
                                "animation_thread": struct.unpack_from("<Q", record, 288)[0],
                                "animation_instance": hex(struct.unpack_from("<Q", record, 296)[0]),
                                "animation_request_id": struct.unpack_from("<i", record, 304)[0],
                                "animation_channel": struct.unpack_from("<i", record, 312)[0],
                                "animation_r9": struct.unpack_from("<i", record, 320)[0],
                                "animation_rate_argument": struct.unpack_from("<f", record, 328)[0],
                                "animation_F8A6": record[336],
                                "animation_copy_stable": bool(struct.unpack_from("<Q", record, 272)[0])
                                and struct.unpack_from("<Q", record, 272)[0] == struct.unpack_from("<Q", record, 344)[0]
                                and not struct.unpack_from("<Q", record, 272)[0] % 2})
                previous = sequence
                special = reader.read(special_log, 112)
                special_sequence = struct.unpack_from("<Q", special)[0]
                if (special_sequence and not special_sequence % 2
                        and special_sequence != previous_special
                        and special_sequence == struct.unpack("<Q", reader.read(special_log, 8))[0]):
                    special_events.append({"observed_monotonic_s": time.monotonic(),
                                           "sequence": special_sequence,
                                           "parent_caller_rva": hex(struct.unpack_from("<Q", special, 8)[0] - BASE),
                                           "pc": hex(struct.unpack_from("<Q", special, 16)[0]),
                                           "setter_return_rva": "0x1f625a",
                                           "static_callsite_rva": "0x1f6254",
                                           "field_A025": special[24],
                                           "field_9FDC": struct.unpack_from("<f", special, 32)[0],
                                           "field_9FF8": struct.unpack_from("<f", special, 40)[0],
                                           "field_9F58": struct.unpack_from("<f", special, 48)[0],
                                           "parameter": struct.unpack_from("<f", special, 56)[0],
                                           "branch_angle_radians": struct.unpack_from("<f", special, 64)[0],
                                           "query_height": struct.unpack_from("<f", special, 72)[0],
                                           "query_normal": struct.unpack_from("<4f", special, 80),
                                           "requested_world_at_setter": struct.unpack_from("<4f", special, 96),
                                           "poll_context": records[-1] if records else None})
                    previous_special = special_sequence
                rate_record = reader.read(rate_log, 48)
                rate_sequence, rate_caller, rate_thread, rate_instance = struct.unpack_from("<4Q", rate_record)
                if rate_sequence and not rate_sequence % 2 and rate_sequence == struct.unpack("<Q", reader.read(rate_log, 8))[0]:
                    if rate_instance != channel:
                        raise ValueError("Rate shim logged another animation channel")
                    returned = struct.unpack_from("<f", rate_record, 32)[0]
                    field_rate = struct.unpack_from("<f", rate_record, 40)[0]
                    rate_events[(rate_caller - BASE, rate_thread, field_rate, returned)] += 1
            time.sleep(0.01)
        moving = [r for r in records if math.hypot(*r["vec"][:3]) > 1e-5]
        states = {(tuple(r["ring_latest_axes"]), r["F8A6"], r["F8AD"], r["speed"]) for r in moving}
        animation_events: dict[int, dict[str, object]] = {}
        segments = []
        for r in records:
            if not any(r["ring_latest_axes"]):
                continue
            key = (tuple(r["ring_latest_axes"]), r["speed"], r["F8A6"], r["F8AD"])
            if not segments or key != segments[-1][0] or r["t"] - segments[-1][1][-1]["t"] > 0.2:
                segments.append((key, []))
            segments[-1][1].append(r)
        world_segments = []
        for key, rows in segments:
            elapsed = rows[-1]["t"] - rows[0]["t"]
            if elapsed < 1:
                continue
            distance = math.hypot(rows[-1]["world"][0] - rows[0]["world"][0], rows[-1]["world"][2] - rows[0]["world"][2])
            path = sum(math.hypot(b["world"][0] - a["world"][0], b["world"][2] - a["world"][2]) for a, b in zip(rows, rows[1:]))
            world_segments.append({"state": key, "elapsed": elapsed, "start": rows[0]["world"], "end": rows[-1]["world"],
                                   "xz_distance": distance, "xz_speed": distance / elapsed, "xz_path_distance": path,
                                   "xz_path_speed": path / elapsed, "height_range": max(r["world"][1] for r in rows) - min(r["world"][1] for r in rows),
                                   "median_dt": statistics.median(r["dt"] for r in rows),
                                   "median_step": statistics.median(r["step"] for r in rows),
                                   "channel_rates": dict(Counter(r["channel_rate"] for r in rows)),
                                   "downstream_rates": dict(Counter(r["downstream_rate"] for r in rows)),
                                   "phase_start_end": [rows[0]["animation_phase"], rows[-1]["animation_phase"]],
                                   "median_kcc_per_dt": statistics.median(math.hypot(r["vec"][0], r["vec"][2]) / r["dt"] for r in rows if r["dt"] > 0)})
        for r in records:
            if r["animation_sequence"] and r["animation_copy_stable"]:
                animation_events.setdefault(r["animation_sequence"], r)
        collision_samples = []
        for index, row in enumerate(records):
            delta = [row["world"][j] - records[index - 1]["world"][j] for j in range(3)] if index else [0.0] * 3
            collision_samples.append({key: row[key] for key in
                                      ("t", "sequence", "world", "player_world", "target_world", "vec",
                                       "speed", "dt", "ring_latest_axes", "kcc_ground_fields", "kcc_step_fields", "kcc_contact_flags",
                                       "active_clip_id", "animation_phase", "downstream_rate")}
                                     | {key: row[key] for key in
                                        ("requested_world", "field_A025", "field_A021", "field_A01E", "field_A04C", "field_A03C",
                                         "field_9FDC", "field_9FF8", "field_9F58",
                                         "production_caller_rva", "animation_request_id", "animation_caller_rva")}
                                     | {"delta_world": delta,
                                        "suspect_vertical": suspect_vertical(delta[1], row["world"][1], records[0]["world"][1]),
                                        "on_ground": all(value == 0.0 for value in row["kcc_ground_fields"])})
        print(json.dumps({"calls_observed": {hex(k): v for k, v in calls.items()},
                          "collision_samples": collision_samples,
                          "special_events": special_events,
                          "special_calls": previous_special // 2,
                          "world_position_source": "Bullet ghost +0x40; poll after submission log, non-atomic",
                          "world_segments": world_segments,
                          "downstream_rate_events": [{"caller_rva": hex(key[0]), "thread": key[1],
                                                      "channel_rate": key[2], "returned_rate": key[3],
                                                      "samples": count} for key, count in rate_events.items()],
                          "submission_count": previous // 2, "records": records[:5],
                          "animation_events": [{key: r[key] for key in
                                                ("t", "animation_sequence", "animation_caller_rva",
                                                 "animation_thread", "animation_request_id", "animation_channel",
                                                 "animation_rate_argument", "animation_F8A6")}
                                               for r in list(animation_events.values())[:100]],
                          "moving_records": [next(r for r in moving if
                                               (tuple(r["ring_latest_axes"]), r["F8A6"], r["F8AD"], r["speed"]) == state)
                                             for state in sorted(states)]}))
    finally:
        try:
            write(rate_log + 0x100, b"\x00")
        finally:
            try:
                if struct.unpack("<Q", reader.read(pc, 8))[0] == pc_table:
                    write(pc, struct.pack("<Q", pc_vptr))
            finally:
                try:
                    if struct.unpack("<Q", reader.read(channel, 8))[0] == channel_table:
                        write(channel, struct.pack("<Q", channel_vptr))
                finally:
                    try:
                        if struct.unpack("<Q", reader.read(kcc, 8))[0] == table:
                            write(kcc, struct.pack("<Q", original_vptr))
                    finally:
                        api.CloseHandle(handle)
        if struct.unpack("<Q", reader.read(kcc, 8))[0] != original_vptr:
            raise RuntimeError("KCC vptr restoration failed or another tool changed it")
        if struct.unpack("<Q", reader.read(pc, 8))[0] != pc_vptr:
            raise RuntimeError("Player vptr restoration failed or another tool changed it")
        if struct.unpack("<Q", reader.read(channel, 8))[0] != channel_vptr:
            raise RuntimeError("Animation channel vptr restoration failed")
        print(json.dumps({"status": "restored", "private_page": hex(page)}), flush=True)
        # ponytail: retain 12 KiB until process exit; free only after a proven quiescence protocol.


def main() -> None:
    if sys.argv[1:] == ["self-check"]:
        assert not suspect_vertical(0.5, 3.4, 1.4)
        assert suspect_vertical(-0.51, 1.4, 1.4)
        assert suspect_vertical(0.0, 13.4, 1.4)
        import capstone
        code = shim(0x12340000, BASE + 0x72A5F0, 0x213A7890, 0x12341A00, 0x12341B00)
        instructions = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(code[:-8], 0))
        assert sum(i.size for i in instructions) == len(code) - 8
        assert [i.mnemonic for i in instructions[:3]] == ["pushfq", "push", "push"]
        assert [i.mnemonic for i in instructions[-5:]] == ["pop", "pop", "pop", "popfq", "jmp"]
        assert struct.unpack("<Q", code[-8:])[0] == BASE + 0x72A5F0
        producer = producer_shim(0x12341900, BASE + 0x1E9980)
        assert sum(i.size for i in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(producer[:-8], 0)) == len(producer) - 8
        animation = animation_shim(0x12341B00, BASE + 0x1DDC10)
        assert sum(i.size for i in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(animation[:-8], 0)) == len(animation) - 8
        assert len(code) < 0x400 and len(producer) < 0x200 and len(animation) < 0x200
        special = special_shim(0x12342400, BASE + 0x1E9980)
        decoded = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(special[:-8], 0))
        assert sum(i.size for i in decoded) == len(special) - 8 < 0x400
        branch = next(i for i in decoded if i.mnemonic == "jne")
        assert next(i for i in decoded if hex(i.address) == branch.op_str).mnemonic == "pop"
        assert any(i.op_str.endswith("[rsp + 0x188]") for i in decoded)
        rate = rate_shim(0x12341E00, BASE + 0x6C6C80)
        rate_instructions = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(rate, 0))
        assert sum(i.size for i in rate_instructions) == len(rate) and len(rate) < 0x200
        assert rate_instructions[-1].mnemonic == "ret"
        print("self-check passed")
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("pc", type=lambda s: int(s, 0))
    parser.add_argument("seconds", type=float)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 60:
        parser.error("seconds must be finite and within 0..60")
    reader = ProcessReader(args.pid)
    try:
        trace(reader, args.pid, args.pc, args.seconds, producer_shim, rate_shim)
    finally:
        reader.close()


if __name__ == "__main__":
    main()
