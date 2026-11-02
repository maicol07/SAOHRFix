"""Bounded player-only terrain trace. Original calls and terrain results preserved.

Private player method copies intercept integration, surface query and Y stores.
No Bullet response copies, contact latches or ghost writes.
--sprint-requested leaves movement vanilla to establish the first-query path.
--extra probes a native physical substep after vanilla and a capsule sweep.
Run self-check before live use; private pages remain until game exit.
"""
from __future__ import annotations

import argparse
import ctypes as ct
from ctypes import wintypes as wt
import json
import struct
import sys

import capstone

from movement_probe import resolve
from pre_projection import relocate
from run_perturb import RUN_BASELINES, animation_rate_shim, perturb_shim
from runtime_read import BASE, MemoryRegion, ProcessReader
from walk_trace import rate_shim, trace

CAPACITY = 8192
STRIDE = 512
STAGES = {1: 'setter', 2: 'integration', 3: 'prepare', 4: 'surface',
          5: 'surface_segment', 6: 'requested_Y_store', 7: 'physical_update',
          8: 'KCC_submission', 9: 'target_Y_store',
          10: 'vanilla_physical', 11: 'extra_physical'}


def event_shim(header: int, records: int, pc: int, kcc: int,
               original: int, stage: int) -> bytes:
    """Preserve the Windows ABI, including all five stack arguments of the query."""
    code = bytearray.fromhex('41 54 41 55 41 56 41 57 48 81 EC E8 00 00 00')
    labels: dict[str, int] = {}
    jumps: list[tuple[int, str]] = []

    def emit(value: str) -> None: code.extend(bytes.fromhex(value))
    def imm(op: str, value: int) -> None:
        emit(op); code.extend(struct.pack('<Q', value))
    def jump(op: str, label: str) -> None:
        emit(op); jumps.append((len(code), label)); code.extend(b'\0' * 4)
    def copy(source: str, offset: int, destination: int) -> None:
        emit(source); code.extend(struct.pack('<i', offset))
        emit('49 89 85'); code.extend(struct.pack('<i', destination))
    def snapshot(offset: int) -> None:
        imm('49 BB', pc)
        for source, destination in [(0x9DE0, 0), (0x9DF0, 16), (0x9E10, 32), (0x9E20, 48)]:
            for j in (0, 8): copy('49 8B 83', source + j, offset + destination + j)
        copy('49 8B 83', 0x9F24, offset + 64)
        for i, source in enumerate((0xA025, 0xA04C, 0xA01E, 0xA021, 0xA047)):
            emit('41 0F B6 83'); code.extend(struct.pack('<i', source))
            emit('41 88 85'); code.extend(struct.pack('<i', offset + 72 + i))

    for reg in range(6):
        emit(f'F3 0F 7F {0x84 + 8 * reg:02X} 24'); code.extend(struct.pack('<i', 0xD0 if reg == 0 else 0x40 + reg * 16))
    for op, offset in [('48 89 8C 24', 0xA0), ('48 89 94 24', 0xA8),
                       ('4C 89 84 24', 0xB0), ('4C 89 8C 24', 0xB8)]:
        emit(op); code.extend(struct.pack('<i', offset))
    for index in range(5):
        emit('48 8B 84 24'); code.extend(struct.pack('<i', 0x130 + index * 8))
        emit('48 89 44 24'); code.append(0x20 + index * 8)
    emit('45 31 ED')
    imm('49 BC', header)
    emit('B8 01 00 00 00 F0 49 0F C1 04 24 48 3D'); code.extend(struct.pack('<I', CAPACITY))
    jump('0F 83', 'call')
    emit('49 89 C6 49 FF C6 48 C1 E0 09'); imm('49 BD', records); emit('49 01 C5 4D 89 75 00')
    emit('65 48 8B 04 25 48 00 00 00 49 89 45 08')
    emit('41 C7 45 18'); code.extend(struct.pack('<I', stage))
    copy('48 8B 84 24', 0x108, 32)
    if stage == 1:
        emit('B8 01 00 00 00 F0 49 0F C1 44 24 08 48 FF C0')
    else:
        emit('49 8B 44 24 08')
    emit('49 89 45 28')
    copy('48 8B 84 24', 0x60, 80)  # original XMM2 low float
    copy('49 8B 84 24', 16, 88)  # setter input before optional multiplier
    snapshot(96)
    if stage in (1, 8):
        emit('4C 8B 9C 24 A8 00 00 00')
        for j in (0, 8): copy('49 8B 83', j, 288 + j)
    elif stage == 5:
        for source, dest in [(0xA8, 288), (0xB0, 304)]:
            emit('4C 8B 9C 24'); code.extend(struct.pack('<i', source))
            for j in (0, 8): copy('49 8B 83', j, dest + j)
    elif stage == 6:
        emit('4C 8B 9C 24 A0 00 00 00 49 8B 03 49 89 85 80 01 00 00')
        copy('49 8B 83', 8, 392)
        copy('48 8B 84 24', 0x50, 400)  # original XMM1 supplying component Y
    elif stage in (7, 10, 11):
        imm('49 BB', kcc); emit('4D 8B 5B 10')
        for j in (0, 8): copy('49 8B 83', 0x40 + j, 288 + j)
        imm('49 BB', kcc)
        for j in (0, 8): copy('49 8B 83', 0x50 + j, 320 + j)
    labels['call'] = len(code)
    for op, offset in [('48 8B 8C 24', 0xA0), ('48 8B 94 24', 0xA8),
                       ('4C 8B 84 24', 0xB0), ('4C 8B 8C 24', 0xB8)]:
        emit(op); code.extend(struct.pack('<i', offset))
    for reg in range(6):
        emit(f'F3 0F 6F {0x84 + 8 * reg:02X} 24'); code.extend(struct.pack('<i', 0xD0 if reg == 0 else 0x40 + reg * 16))
    imm('48 B8', original); emit('FF D0 48 89 84 24 C0 00 00 00 F3 0F 7F 84 24 D0 00 00 00')
    emit('4D 85 ED'); jump('0F 84', 'return')
    snapshot(192)
    if stage == 5:
        emit('4C 8B 9C 24 B8 00 00 00')
        for j in (0, 8): copy('49 8B 83', j, 336 + j)
        emit('4C 8B 5C 24 20')
        for j in (0, 8): copy('49 8B 83', j, 352 + j)
    elif stage in (7, 10, 11):
        imm('49 BB', kcc); emit('4D 8B 5B 10')
        for j in (0, 8): copy('49 8B 83', 0x40 + j, 304 + j)
    copy('48 8B 84 24', 0xC0, 368)
    emit('4D 89 75 10')
    labels['return'] = len(code)
    emit('48 8B 84 24 C0 00 00 00 F3 0F 6F 84 24 D0 00 00 00 48 81 C4 E8 00 00 00 41 5F 41 5E 41 5D 41 5C C3')
    for offset, label in jumps: struct.pack_into('<i', code, offset, labels[label] - offset - 4)
    return bytes(code)


def extra_shim(pc: int, kcc: int, baseline_bits: int, first: int, extra: int,
               rate_gate: int) -> bytes:
    """Diagnostic A+C: vanilla action, native capsule preflight, optional dt=0 action."""
    code = bytearray.fromhex('41 54 41 55 41 56 41 57 48 81 EC A8 01 00 00')
    exits: list[int] = []
    def emit(value: str) -> None: code.extend(bytes.fromhex(value))
    def imm(op: str, value: int) -> None: emit(op); code.extend(struct.pack('<Q', value))
    def reject(op: str) -> None:
        emit(op); exits.append(len(code)); code.extend(b'\0' * 4)
    def call(address: int) -> None: imm('48 B8', address); emit('FF D0')
    imm('49 BC', kcc); imm('49 BE', pc)
    emit('49 89 D5')
    # Keep the exact vanilla submission before the first physical action.
    emit('41 0F B6 84 24 E3 00 00 00 89 84 24 78 01 00 00')
    emit('41 0F 28 44 24 50')
    emit('0F 29 84 24 50 01 00 00 4D 8B 7C 24 10')
    emit('41 0F 28 47 40 0F 29 84 24 60 01 00 00')
    emit('83 BC 24 78 01 00 00 01 75 11')
    imm('48 B8', rate_gate); emit('C7 00 01 00 00 00 90')
    call(first)
    emit('83 BC 24 78 01 00 00 01'); reject('0F 85')
    for offset, value in [(0xF8A6, 1), (0xF8AD, 0), (0xA9E9, 0xFF), (0xA9F0, 0xFE)]:
        emit('41 80 BE'); code.extend(struct.pack('<iB', offset, value)); reject('0F 85')
    emit('41 81 BE 24 9F 00 00'); code.extend(struct.pack('<I', baseline_bits)); reject('0F 85')
    # Only an unchanged, horizontal vanilla submission qualifies for this probe.
    # shortcut: nonzero terrain Y keeps vanilla only; broaden after slope validation.
    emit('F3 0F 10 84 24 54 01 00 00 0F 54 05'); code.extend(struct.pack('<i', 0))
    abs_fix = len(code) - 4
    emit('0F 2F 05'); tolerance_fix = len(code); code.extend(b'\0' * 4); reject('0F 87')
    # Reject if the first native action was blocked/projected in X or Z.
    emit('41 0F 28 47 40 0F 5C 84 24 60 01 00 00 0F 5C 84 24 50 01 00 00')
    emit('0F 54 05'); error_abs_fix = len(code); code.extend(b'\0' * 4)
    emit('0F 2F 05'); error_fix = len(code); code.extend(b'\0' * 4); reject('0F 87')
    emit('0F C6 C0 AA 0F 2F 05'); error_z_fix = len(code); code.extend(b'\0' * 4); reject('0F 87')
    emit('0F 28 84 24 50 01 00 00 0F 59 05'); factor_fix = len(code); code.extend(b'\0' * 4)
    emit('0F 29 84 24 40 01 00 00')
    # Copy the ghost transform into two stack transforms; never write the ghost.
    for offset in (0, 16, 32, 48):
        emit(f'41 0F 28 47 {0x10 + offset:02X} 0F 29 84 24')
        code.extend(struct.pack('<i', 0xC0 + offset))
        emit('0F 29 84 24'); code.extend(struct.pack('<i', 0x100 + offset))
    emit('0F 28 84 24 40 01 00 00 0F 58 84 24 30 01 00 00 0F 29 84 24 30 01 00 00')
    # Original closest-not-me callback: native mask/group, self, opposing travel.
    emit('31 C0')
    for offset in range(0x30, 0xC0, 8):
        emit('48 89 84 24'); code.extend(struct.pack('<i', offset))
    imm('48 B8', BASE + 0x8C55C0); emit('48 89 44 24 30 C7 44 24 38 00 00 80 3F')
    emit('49 8B 87 C8 00 00 00 8B 40 08 89 44 24 3C 4C 89 BC 24 90 00 00 00')
    emit('0F 57 C0 0F 5C 84 24 40 01 00 00 0F 29 84 24 A0 00 00 00')
    # Match native forward sweep margin handling and restore immediately.
    emit('49 8B 4C 24 18 48 8B 01 FF 50 50 F3 0F 11 84 24 8C 01 00 00')
    emit('0F 28 C8 F3 41 0F 58 4C 24 48 49 8B 4C 24 18 48 8B 01 FF 50 48')
    emit('4C 89 E9 49 8B 54 24 18 4C 8D 84 24 C0 00 00 00 4C 8D 8C 24 00 01 00 00')
    emit('48 8D 44 24 30 48 89 44 24 20 F3 41 0F 10 45 54 F3 0F 11 44 24 28')
    call(BASE + 0x6F8890)
    emit('F3 0F 10 8C 24 8C 01 00 00 49 8B 4C 24 18 48 8B 01 FF 50 48')
    emit('48 83 BC 24 80 00 00 00 00'); reject('0F 85')  # callback hit object
    imm('48 B8', rate_gate); emit('C7 00 00 00 00 00')
    emit('4C 89 E1 48 8D 94 24 40 01 00 00'); call(BASE + 0x72A5F0)
    emit('4C 89 E1 4C 89 EA 0F 57 D2'); call(extra)
    end = len(code)
    emit('48 81 C4 A8 01 00 00 41 5F 41 5E 41 5D 41 5C C3')
    for fix in exits: struct.pack_into('<i', code, fix, end - fix - 4)
    code.extend(b'\x90' * (-len(code) % 16))
    constants = len(code)
    code.extend(struct.pack('<4I', *([0x7FFFFFFF] * 4)))
    code.extend(struct.pack('<4f', *([0.001] * 4)))
    code.extend(struct.pack('<4f', *([0.0002] * 4)))
    code.extend(struct.pack('<4f', 0.25, 0, 0.25, 0))
    for fix, target in [(abs_fix, constants), (error_abs_fix, constants),
                         (tolerance_fix, constants + 16), (error_fix, constants + 32),
                         (error_z_fix, constants + 32), (factor_fix, constants + 48)]:
        struct.pack_into('<i', code, fix, target - fix - 4)
    return bytes(code)


def setup(reader: ProcessReader, handle: int, pc: int, kcc: int,
          extra: bool, baseline_bits: int) -> dict[str, int]:
    api = reader.api
    address = BASE - 0x70000000
    region = MemoryRegion()
    page = 0
    while address < BASE + 0x70000000 and api.VirtualQueryEx(handle, address, ct.byref(region), ct.sizeof(region)):
        end = (region.base or 0) + region.size
        if end <= address: raise ValueError('Non-progressing allocation search')
        aligned = (max(region.base or 0, address) + 0xFFFF) & ~0xFFFF
        if region.state == 0x10000 and end - aligned >= 0x20000:
            page = api.VirtualAllocEx(handle, aligned, 0x20000, 0x3000, 0x40)
            if page: break
        address = end
    if not page: raise OSError('No bounded near-image code region')
    records = api.VirtualAllocEx(handle, None, CAPACITY * STRIDE, 0x3000, 4)
    if not records: raise ct.WinError(ct.get_last_error())
    header = page + 0x10000

    def write(address: int, data: bytes) -> None:
        count = ct.c_size_t(); buffer = ct.create_string_buffer(data)
        if not api.WriteProcessMemory(handle, address, buffer, len(data), ct.byref(count)) or count.value != len(data):
            raise ct.WinError(ct.get_last_error())

    # Chained native bodies have tail jumps and cold blocks; the sentinel is never copied.
    for rva, size, offset, calls in [
        (0x20B2A0, 0x38C, 0, {0x20B605: page + 0x1000}),
        (0x1EAE70, 0x112, 0x1000, {0x1EAF59: page + 0x4000}),
        (0x1F5B30, 0xB20, 0x2000, {0x1F5CC0: page + 0x3000, 0x1F5D2D: page + 0x3000,
                                  0x1F5E15: page + 0x9000,
                                  0x1F663D: page + 0x7000}),
        (0x31EE00, 0x185, 0x3000, {0x31EED9: page + 0x6000})]:
        raw = reader.read(BASE + rva, size)
        if rva == 0x1F5B30:
            store = 0x1F5E15 - rva
            expected = bytes.fromhex('0F 29 97 20 9E 00 00')
            if raw[store:store + 7] != expected: raise ValueError('Unverified target Y store')
            # RAX/R11 are dead before the following direct call in this exact context.
            write(page + 0xE000, expected + b'\xC3')
            raw = raw[:store] + bytes.fromhex('E8 00 00 00 00 90 90') + raw[store + 7:]
        write(page + offset, relocate(raw + b'\xC3', BASE + rva, page + offset,
                                     {BASE + call: target for call, target in calls.items()})[:-1])
    for offset, original, stage in [(0x4000, BASE + 0x1F69B0, 2),
                                    (0x5000, page + 0x2000, 4),
                                    (0x6000, BASE + 0x6CB920, 5),
                                    (0x7000, BASE + 0x164840, 6),
                                    (0x8000, BASE + 0x1E9980, 1),
                                    (0x9000, page + 0xE000, 9),
                                    (0xA000, BASE + 0x259430, 3),
                                    (0xB000, page + 0xF000 if extra else BASE + 0x58D340, 7),
                                    (0xD000, BASE + 0x72A5F0, 8)]:
        code = event_shim(header, records, pc, kcc, original, stage)
        if len(code) >= 4096: raise ValueError('Terrain shim exceeds private slot')
        write(page + offset, code)
    if extra:
        write(header + 24, struct.pack('<I', 1))
        write(page + 0xF000, extra_shim(pc, kcc, baseline_bits, page + 0x11000, page + 0x12000,
                                      header + 24))
        for offset, original, stage in [(0x11000, BASE + 0x58D340, 10),
                                        (0x12000, BASE + 0x58D340, 11)]:
            write(page + offset, event_shim(header, records, pc, kcc, original, stage))
    if not api.FlushInstructionCache(handle, page, 0x13000): raise ct.WinError(ct.get_last_error())
    return {'page': page, 'header': header, 'records': records}


def dump(reader: ProcessReader, state: dict[str, int]) -> None:
    count = struct.unpack('<Q', reader.read(state['header'], 8))[0]
    if count > CAPACITY: raise ValueError('Terrain trace ring overflow; discard capture')
    for index in range(count):
        raw = reader.read(state['records'] + index * STRIDE, STRIDE)
        sequence, thread, complete, stage, caller, producer = struct.unpack_from('<6Q', raw)
        if not complete: continue
        if sequence != index + 1 or sequence != complete or stage not in STAGES:
            raise ValueError('Invalid published terrain event')
        caller_rva = caller - BASE
        for offset, size, rva in [(0, 0x38C, 0x20B2A0), (0x1000, 0x112, 0x1EAE70),
                                  (0x2000, 0xB20, 0x1F5B30), (0x3000, 0x185, 0x31EE00)]:
            if state['page'] + offset <= caller < state['page'] + offset + size:
                caller_rva = rva + caller - state['page'] - offset
                break
        def snapshot(offset: int) -> dict[str, object]:
            return {**{name: struct.unpack_from('<4f', raw, offset + delta) for name, delta in
                       [('current', 0), ('integrated', 16), ('requested', 32), ('target', 48)]},
                    'parameter': struct.unpack_from('<f', raw, offset + 64)[0],
                    **{name: raw[offset + 72 + i] for i, name in enumerate(('A025', 'A04C', 'A01E', 'A021', 'A047'))}}
        payload: dict[str, object] = {}
        if stage in (1, 8): payload['input'] = struct.unpack_from('<4f', raw, 288)
        if stage == 1:
            payload['original_parameter'] = struct.unpack_from('<f', raw, 88)[0]
            payload['effective_parameter'] = struct.unpack_from('<f', raw, 80)[0]
        if stage == 5:
            for name, offset in [('start', 288), ('end', 304), ('hit', 336), ('normal', 352)]:
                payload[name] = struct.unpack_from('<4f', raw, offset)
            payload['result'] = struct.unpack_from('<i', raw, 368)[0]
            if payload['result'] < 0:
                payload['hit'] = None; payload['normal'] = None
        if stage == 6:
            payload['destination'] = hex(struct.unpack_from('<Q', raw, 384)[0])
            payload['component'] = struct.unpack_from('<I', raw, 392)[0]
            payload['query_Y_argument'] = struct.unpack_from('<f', raw, 400)[0]
        if stage in (7, 10, 11):
            payload['ghost_before'] = struct.unpack_from('<4f', raw, 288)
            payload['ghost_after'] = struct.unpack_from('<4f', raw, 304)
            payload['KCC_requested'] = struct.unpack_from('<4f', raw, 320)
        print(json.dumps({'terrain_trace': 'event', 'sequence': sequence, 'thread': thread,
                          'stage': STAGES[stage], 'caller': hex(caller), 'producer_sequence': producer,
                          'caller_rva': hex(caller_rva),
                          'before': snapshot(96), 'after': snapshot(192), **payload}), flush=True)
    print(json.dumps({'terrain_trace': 'summary', 'events': count, 'overflow': 0}), flush=True)


def self_check() -> None:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
    for stage in STAGES:
        code = event_shim(0x150010000, 0x25000000, 0x21000000, 0x33000000, BASE + 0x1F69B0, stage)
        decoded = list(md.disasm(code, 0)); starts = {i.address for i in decoded}
        assert sum(i.size for i in decoded) == len(code) < 4096
        assert all(i.operands[0].imm in starts for i in decoded if i.group(capstone.CS_GRP_JUMP))
        assert decoded[-1].mnemonic == 'ret'
    code = extra_shim(0x21000000, 0x33000000, 0x3E2D712B, 0x150011000, 0x150012000,
                      0x150010018)
    decoded = []
    for instruction in md.disasm(code, 0):
        decoded.append(instruction)
        if instruction.mnemonic == 'ret': break
    starts = {i.address for i in decoded}
    assert decoded[-1].mnemonic == 'ret' and len(code) < 4096
    assert all(i.operands[0].imm in starts for i in decoded if i.group(capstone.CS_GRP_JUMP))
    assert len(code) % 16 == 0
    assert all((i.address + i.size + o.mem.disp) % 16 == 0
               for i in decoded for o in i.operands
               if o.type == capstone.CS_OP_MEM and o.mem.base == capstone.x86.X86_REG_RIP)
    print('self-check passed')


def main() -> None:
    if sys.argv[1:] == ['self-check']: self_check(); return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid', type=int)
    parser.add_argument('pc', type=lambda s: int(s, 0))
    parser.add_argument('seconds', type=float)
    parser.add_argument('--movement', type=float, choices=(1, 1.25), default=1)
    parser.add_argument('--sprint-requested', action='store_true')
    parser.add_argument('--extra', action='store_true', help='Vanilla-first A+C diagnostic substep')
    parser.add_argument('--baseline-bits', type=lambda s: int(s, 0), choices=RUN_BASELINES, default=RUN_BASELINES[0])
    args = parser.parse_args()
    if args.sprint_requested and args.movement != 1: parser.error('Preservation probe must keep movement vanilla')
    if args.extra and (args.movement != 1 or args.sprint_requested): parser.error('Extra requires vanilla first contribution')
    if not 0 < args.seconds <= 30: parser.error('Bounded terrain trace requires 0..30 seconds')
    reader = ProcessReader(args.pid); api = reader.api
    api.VirtualAllocEx.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_size_t, wt.DWORD, wt.DWORD]
    api.VirtualAllocEx.restype = ct.c_void_p
    api.WriteProcessMemory.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.POINTER(ct.c_size_t)]
    api.WriteProcessMemory.restype = wt.BOOL
    api.FlushInstructionCache.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_size_t]; api.FlushInstructionCache.restype = wt.BOOL
    identity = resolve(reader, args.pc); kcc = identity[2]
    for slot, rva in [(0x168, 0x20B2A0), (0x170, 0x259430), (0x178, 0x1F5B30)]:
        if struct.unpack('<Q', reader.read(BASE + 0x80AE08 + slot, 8))[0] != BASE + rva:
            raise ValueError('Unverified player terrain method')
    handle = api.OpenProcess(0x438, False, args.pid)
    if not handle: raise ct.WinError(ct.get_last_error())
    try:
        state = setup(reader, handle, args.pc, kcc, args.extra, args.baseline_bits)
        owner = struct.unpack('<Q', reader.read(args.pc + 0x4C0, 8))[0]
        controller = struct.unpack('<Q', reader.read(owner + 0x108, 8))[0]
        channel = struct.unpack('<Q', reader.read(controller + 0x2F0, 8))[0]
        def animation(log: int, original: int) -> bytes:
            return animation_rate_shim(log, original, args.pc, identity[0], owner, controller,
                                       channel, 1, 1.25, args.baseline_bits, state['header'] + 24)
        def production(log: int, original: int) -> bytes:
            prefix = bytes.fromhex('50 41 52 49 BA') + struct.pack('<Q', state['header'] + 16)
            prefix += bytes.fromhex('66 0F 7E D0 41 89 02 41 5A 58')
            code = prefix + perturb_shim(log, state['page'] + 0x8000, args.pc, identity[0],
                                         args.movement, args.baseline_bits)
            if len(code) > 0x200: raise ValueError('Terrain producer exceeds private code slot')
            return code
        print(json.dumps({'terrain_trace': 'setup', 'movement': args.movement,
                          'requested_goal': 1.25 if args.sprint_requested or args.extra else args.movement,
                          'extra_enabled': args.extra, 'page': hex(state['page'])}), flush=True)
        trace(reader, args.pid, args.pc, args.seconds, production, animation if args.extra else rate_shim,
              {0x08: state['page'] + 0xB000, 0x18: state['page'] + 0xD000},
              {0x168: state['page'], 0x170: state['page'] + 0xA000, 0x178: state['page'] + 0x5000})
        dump(reader, state)
    finally:
        api.CloseHandle(handle); reader.close()


if __name__ == '__main__': main()
