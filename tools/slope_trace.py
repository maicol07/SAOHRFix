"""Bounded player KCC update records, shared sequence for pre/post and contact.

Instance vtable hooks only. No executable/image patch; original collision response.
Records stay in private memory until exit; original physics calls preserved.
Optional movement/rate perturbation is diagnostic only. The contact fallback
failed the wall-ascent gate; it is not a validated Sprint safety mechanism.
Pre-projection mode deboosts a private forward target before the original response.
Run self-check before live use. Output is diagnostic fields, not process dumps.
"""
from __future__ import annotations

import argparse
import ctypes as ct
from ctypes import wintypes as wt
from collections import Counter
import json
import math
import struct
import sys
from pathlib import Path

from movement_probe import resolve
from run_perturb import RUN_BASELINES, animation_rate_shim, perturb_shim
from runtime_read import BASE, ProcessReader
from walk_trace import rate_shim, trace

CAPACITY = 4096
STRIDE = 2048
TARGETS = {0x08: 0x58D340, 0x38: 0x72A160, 0x40: 0x729EF0, 0x60: 0x5875A0}
SNAPSHOTS = {'update_before': 64, 'update_after': 224,
             'prestep_before': 384, 'prestep_after': 544,
             'step_before': 704, 'step_after': 864}


def build_shim(page: int, slot: int, movement: float, animation: float,
               pc: int = 0, baseline_bits: int = RUN_BASELINES[0],
               suppress_on_contact: bool = False, call_target: int | None = None) -> bytes:
    """Generate one of the four verified ABI wrappers; no shared code detours."""
    code = bytearray.fromhex('41 54 41 55 41 56 41 57 48 81 EC D8 00 00 00')
    labels: dict[str, int] = {}
    jumps: list[tuple[int, str]] = []

    def emit(value: str) -> None:
        code.extend(bytes.fromhex(value))

    def jump(op: str, label: str) -> None:
        emit(op); jumps.append((len(code), label)); code.extend(b'\0' * 4)

    def imm(op: str, value: int) -> None:
        emit(op); code.extend(struct.pack('<Q', value))

    def store(offset: int) -> None:
        emit('49 89 85'); code.extend(struct.pack('<i', offset))

    def copy(source: str, source_offset: int, destination: int) -> None:
        emit(source); code.extend(struct.pack('<i', source_offset)); store(destination)

    def snapshot(offset: int) -> None:
        emit('4D 8B 5E 10')  # r11 = ghost
        for j in (0, 8): copy('49 8B 83', 0x40 + j, offset + j)
        for src, dst, size in ((0x70, 16, 16), (0x90, 32, 16), (0x20, 48, 48),
                               (0x50, 96, 32), (0xC0, 128, 16), (0xE0, 144, 16)):
            for j in range(0, size, 8): copy('49 8B 86', src + j, offset + dst + j)
        normal_offset = 1920 + ((offset - 64) // 160) * 16
        for j in (0, 8): copy('49 8B 86', 0xD0 + j, normal_offset + j)

    # Save all volatile SIMD arguments, integer arguments, and fifth stack arg.
    for reg in range(6):
        emit(f'F3 0F 7F {0x84 + reg * 8:02X} 24')
        code.extend(struct.pack('<i', 0x40 + reg * 16))
    for op, offset in [('48 89 8C 24', 0xA0), ('48 89 94 24', 0xA8),
                       ('4C 89 84 24', 0xB0), ('4C 89 8C 24', 0xB8)]:
        emit(op); code.extend(struct.pack('<i', offset))
    emit('48 8B 84 24 20 01 00 00 48 89 44 24 20')
    emit('49 89 CE 45 31 ED')  # r14 = KCC, r13 = nullable record
    imm('49 BC', page + 0x4000)  # header: counter, conflicts, overflow
    emit('65 48 8B 04 25 48 00 00 00 25 FF 00 00 00 48 C1 E0 04')
    imm('49 BA', page + 0x5000)
    emit('4C 01 D0 49 89 C7')  # r15 = per-thread context slot
    if slot == 0x08:
        emit('B8 01 00 00 00 F0 49 0F C1 04 24')
        emit('48 3D'); code.extend(struct.pack('<I', CAPACITY)); jump('0F 83', 'overflow')
        emit('48 89 C2 48 FF C2 48 C1 E0 0B')
        imm('49 BD', page + 0x6000)
        emit('49 01 C5 49 89 55 00 65 48 8B 04 25 48 00 00 00'); store(8)
        emit('31 C0 F0 4D 0F B1 2F'); jump('0F 85', 'conflict')
        emit('66 0F 7E D0'); store(32)
        for offset, value in ((40, movement), (48, animation)):
            emit('B8'); code.extend(struct.pack('<f', value)); store(offset)
        snapshot(SNAPSHOTS['update_before'])
        if suppress_on_contact:
            # shortcut: contact is already projected; this latch cannot prevent the first ascent.
            # Release the diagnostic latch only on an original zero request.
            emit('41 8B 46 50 41 0B 46 54 41 0B 46 58 25 FF FF FF 7F')
            jump('0F 85', 'keep_suppressed')
            emit('31 C0 41 87 44 24 18')
            labels['keep_suppressed'] = len(code)
        copy('49 8B 84 24', 0x18, 2016)
        jump('E9', 'call')
        labels['overflow'] = len(code); emit('F0 49 FF 44 24 10'); jump('E9', 'unrecorded')
        labels['conflict'] = len(code); emit('F0 49 FF 44 24 08')
        labels['unrecorded'] = len(code); emit('45 31 ED')
    else:
        emit('4D 8B 2F 4D 85 ED'); jump('0F 84', 'call')
        emit('65 48 8B 04 25 48 00 00 00 49 3B 45 08'); jump('0F 85', 'bad_context')
        emit('49 83 7C 24 08 00'); jump('0F 85', 'bad_context')
        if slot == 0x60:
            emit('49 8B 45 18 48 83 F8 07'); jump('0F 83', 'callback_overflow')
            emit('49 FF 45 18 48 C1 E0 07 49 01 C5 49 81 C5 00 04 00 00')
            copy('48 8B 84 24', 0xF8, 0)  # original caller
            copy('48 8B 84 24', 0xA8, 8)
            if suppress_on_contact:
                imm('49 BB', BASE + 0x72ADDB)
                copy('48 8B 84 24', 0xF8, 0)
                emit('4C 39 D8'); jump('0F 85', 'no_latch')
                imm('49 BB', pc)
                emit('41 81 BB 24 9F 00 00')
                baseline = struct.unpack('<f', struct.pack('<I', baseline_bits))[0]
                code.extend(struct.pack('<f', baseline * movement))
                jump('0F 85', 'no_latch')
                emit('B8 01 00 00 00 41 87 44 24 18')
                labels['no_latch'] = len(code)
            emit('4C 8B 9C 24 B8 00 00 00')
            for j in (0, 8): copy('49 8B 83', j, 16 + j)  # normal
            # Forward caller's rsp+58 hit fraction; only meaningful at 72ADDB.
            emit('8B 84 24 58 01 00 00 41 89 45 1C')
            emit('4C 8B 9C 24 B0 00 00 00')
            for j in (0, 8): copy('49 8B 83', j, 32 + j)  # hit point
            emit('4C 8B 5C 24 20')
            for j in (0, 8): copy('49 8B 83', j, 48 + j)  # original fifth arg
            for src, dst in ((0x70, 64), (0x90, 80)):
                for j in (0, 8): copy('49 8B 86', src + j, dst + j)
        else:
            snapshot(SNAPSHOTS['prestep_before' if slot == 0x38 else 'step_before'])
        jump('E9', 'call')
        if slot == 0x60:
            labels['callback_overflow'] = len(code); emit('49 FF 45 38')
        labels['bad_context'] = len(code); emit('45 31 ED')
    labels['call'] = len(code)
    for op, offset in [('48 8B 8C 24', 0xA0), ('48 8B 94 24', 0xA8),
                       ('4C 8B 84 24', 0xB0), ('4C 8B 8C 24', 0xB8)]:
        emit(op); code.extend(struct.pack('<i', offset))
    for reg in range(6):
        emit(f'F3 0F 6F {0x84 + reg * 8:02X} 24')
        code.extend(struct.pack('<i', 0x40 + reg * 16))
    imm('48 B8', call_target if call_target is not None else BASE + TARGETS[slot]); emit('FF D0')
    emit('48 89 84 24 C0 00 00 00 F3 0F 7F 44 24 40 4D 85 ED')
    jump('0F 84', 'return')
    if slot == 0x60:
        for src, dst in ((0x70, 96), (0x90, 112)):
            for j in (0, 8): copy('49 8B 86', src + j, dst + j)
    else:
        name = {0x08: 'update_after', 0x38: 'prestep_after', 0x40: 'step_after'}[slot]
        snapshot(SNAPSHOTS[name])
        if slot == 0x08:
            copy('49 8B 84 24', 0x18, 2024)
            emit('49 8B 45 00 49 89 45 10 31 C0 49 87 07')  # publish, clear context
    labels['return'] = len(code)
    emit('48 8B 84 24 C0 00 00 00 F3 0F 6F 44 24 40')
    emit('48 81 C4 D8 00 00 00 41 5F 41 5E 41 5D 41 5C C3')
    for offset, label in jumps: struct.pack_into('<i', code, offset, labels[label] - offset - 4)
    return bytes(code)


def decode_snapshot(record: bytes, offset: int) -> dict[str, object]:
    return {'ghost': struct.unpack_from('<4f', record, offset),
            'current': struct.unpack_from('<4f', record, offset + 16),
            'target': struct.unpack_from('<4f', record, offset + 32),
            'vertical_20_4F': struct.unpack_from('<12f', record, offset + 48),
            'walk_50': struct.unpack_from('<4f', record, offset + 96),
            'normalized_60': struct.unpack_from('<4f', record, offset + 112),
            'contact_C0_CF': list(record[offset + 128:offset + 144]),
            'contact_normal_D0': struct.unpack_from('<4f', record, 1920 + ((offset - 64) // 160) * 16),
            'state_E0_EF': list(record[offset + 144:offset + 160])}


def self_check() -> None:
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    for slot in TARGETS:
        code = build_shim(0x20000000, slot, 1.25, 1.25, 0x213F9890,
                          RUN_BASELINES[1], True)
        ins = list(md.disasm(code, 0))
        assert sum(i.size for i in ins) == len(code) < 4096
        boundaries = {i.address for i in ins}
        assert all(int(i.op_str, 16) in boundaries for i in ins if i.mnemonic.startswith('j'))
        assert ins[-1].mnemonic == 'ret'
        assert len([i for i in ins if i.mnemonic == 'call']) == 1
        assert bytes.fromhex('48 8B 84 24 20 01 00 00 48 89 44 24 20') in code
        for reg in range(6):
            matches = [i for i in ins if i.mnemonic == 'movdqu' and
                       any(o.type == capstone.CS_OP_REG and i.reg_name(o.reg) == f'xmm{reg}' for o in i.operands)]
            assert len(matches) == (4 if reg == 0 else 2)
            assert all(o.mem.disp == 0x40 + reg * 16 for i in matches for o in i.operands
                       if o.type == capstone.CS_OP_MEM)
    assert SNAPSHOTS['step_after'] + 160 == 1024
    assert len(decode_snapshot(bytes(2048), 64)['vertical_20_4F']) == 12
    print('self-check passed')


def summarize(path: Path) -> None:
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    updates = [r for r in rows if r.get('physics_trace') == 'update']
    if not updates: raise ValueError('No synchronized updates')
    polls = next(r for r in rows if 'collision_samples' in r)
    before = lambda r: r['stages']['update_before']['ghost']
    after = lambda r: r['stages']['update_after']['ghost']
    print(json.dumps({'file': str(path), 'updates': len(updates),
                      'start': before(updates[0]), 'end': after(updates[-1]),
                      'max_y': max(after(r)[1] for r in updates),
                      'max_dy': max(after(r)[1] - before(r)[1] for r in updates),
                      'special_calls': polls['special_calls'],
                      'speeds': sorted({r['speed'] for r in polls['moving_records']}),
                      'rate_pairs': sorted({(r['channel_rate'], r['returned_rate']) for r in polls['downstream_rate_events']}),
                      'contact_callers': dict(Counter(c['caller_rva'] for r in updates for c in r['contacts'])),
                      'callback_overflows': sum(r['contact_overflow'] for r in updates),
                      'trace_summary': next(r for r in rows if r.get('physics_trace') == 'summary'),
                      'restored': any(r.get('status') == 'restored' for r in rows)}))


def main() -> None:
    if sys.argv[1:] == ['self-check']: self_check(); return
    if len(sys.argv) == 3 and sys.argv[1] == 'summarize': summarize(Path(sys.argv[2])); return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid', type=int)
    parser.add_argument('pc', type=lambda x: int(x, 0))
    parser.add_argument('seconds', type=float)
    parser.add_argument('movement', type=float, choices=(1, 1.10, 1.15, 1.20, 1.25))
    parser.add_argument('animation', type=float, choices=(1, 1.10, 1.15, 1.20, 1.25))
    parser.add_argument('--baseline-bits', type=lambda x: int(x, 0), choices=RUN_BASELINES, default=RUN_BASELINES[0])
    parser.add_argument('--suppress-on-contact', action='store_true',
                        help='Experimental contact fallback; failed wall-ascent validation')
    parser.add_argument('--pre-projection', action='store_true',
                        help='Experimental player-only forward projection deboost')
    args = parser.parse_args()
    if args.pre_projection and args.suppress_on_contact:
        parser.error('Choose one diagnostic suppression strategy')
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 60: parser.error('seconds must be 0..60')
    reader = ProcessReader(args.pid)
    api = reader.api
    api.VirtualAllocEx.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_size_t, wt.DWORD, wt.DWORD]
    api.VirtualAllocEx.restype = ct.c_void_p
    api.WriteProcessMemory.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.POINTER(ct.c_size_t)]
    api.WriteProcessMemory.restype = wt.BOOL
    api.FlushInstructionCache.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_size_t]
    api.FlushInstructionCache.restype = wt.BOOL
    handle = api.OpenProcess(0x438, False, args.pid)
    if not handle: reader.close(); raise ct.WinError(ct.get_last_error())
    try:
        identity = resolve(reader, args.pc); kcc = identity[2]
        if reader.read(args.pc + 0xA9E9, 1) != b'\xff' or reader.read(args.pc + 0xA9F0, 1) != b'\xfe':
            raise ValueError('Verified selector must be FF/FE before perturbation; reload verified context')
        for slot, target in TARGETS.items():
            actual = struct.unpack('<Q', reader.read(BASE + 0x879BD0 + slot, 8))[0]
            if actual != BASE + target: raise ValueError('Unexpected physics method')
        page = api.VirtualAllocEx(handle, None, 0x6000 + CAPACITY * STRIDE, 0x3000, 0x40)
        if not page: raise ct.WinError(ct.get_last_error())
        entries: dict[int, int] = {}
        projection = None
        if args.pre_projection:
            from pre_projection import prepare
            projection = prepare(reader, handle, page, args.pc, kcc, args.movement, args.baseline_bits)
        for index, slot in enumerate(TARGETS):
            entries[slot] = page + index * 4096
            code = build_shim(page, slot, args.movement, args.animation, args.pc,
                              args.baseline_bits, args.suppress_on_contact,
                              projection['step'] if projection and slot == 0x40 else None)
            if len(code) >= 4096: raise ValueError('Physics shim too large')
            count = ct.c_size_t(); buffer = ct.create_string_buffer(code)
            if not api.WriteProcessMemory(handle, entries[slot], buffer, len(code), ct.byref(count)) or count.value != len(code):
                raise ct.WinError(ct.get_last_error())
        if not api.FlushInstructionCache(handle, page, 0x4000): raise ct.WinError(ct.get_last_error())
        owner = struct.unpack('<Q', reader.read(args.pc + 0x4C0, 8))[0]
        controller = struct.unpack('<Q', reader.read(owner + 0x108, 8))[0]
        channel = struct.unpack('<Q', reader.read(controller + 0x2F0, 8))[0]
        def production(log: int, original: int) -> bytes:
            return perturb_shim(log, original, args.pc, identity[0], args.movement,
                                args.baseline_bits, page + 0x4018 if args.suppress_on_contact or args.pre_projection else None)
        def rate(log: int, original: int) -> bytes:
            if args.animation == 1: return rate_shim(log, original)
            return animation_rate_shim(log, original, args.pc, identity[0], owner, controller,
                                       channel, args.movement, args.animation, args.baseline_bits,
                                       page + 0x4018 if args.suppress_on_contact or args.pre_projection else None)
        print(json.dumps({'physics_trace': 'setup', 'schema': 2,
                          'suppression_enabled': args.suppress_on_contact or args.pre_projection,
                          'pre_projection_enabled': args.pre_projection}), flush=True)
        trace(reader, args.pid, args.pc, args.seconds, production, rate, entries)
        if projection:
            from pre_projection import dump
            dump(reader, projection['page'])
        total, conflicts, overflow = struct.unpack('<3Q', reader.read(page + 0x4000, 24))
        print(json.dumps({'physics_trace': 'summary', 'reserved': total, 'conflicts': conflicts, 'overflow': overflow}), flush=True)
        if conflicts or overflow: raise ValueError('Physics trace context/ring overflow; discard capture')
        for index in range(total):
            address = page + 0x6000 + index * STRIDE
            record = reader.read(address, STRIDE)
            sequence, thread, complete, callbacks = struct.unpack_from('<4Q', record)
            if sequence != index + 1 or complete != sequence: continue  # in-flight update, not published
            if struct.unpack('<Q', reader.read(address + 16, 8))[0] != sequence: raise ValueError('Unstable published update')
            stages = {name: decode_snapshot(record, offset) for name, offset in SNAPSHOTS.items()}
            events = []
            for j in range(min(callbacks, 7)):
                off = 1024 + j * 128
                caller = struct.unpack_from('<Q', record, off)[0] - BASE
                events.append({'caller_rva': hex(caller),
                               'hit_fraction': struct.unpack_from('<f', record, off + 28)[0] if caller == 0x72ADDB else None,
                               **{name: struct.unpack_from('<4f', record, off + pos) for name, pos in
                                  [('point', 32), ('argument5', 48), ('current_before', 64),
                                   ('target_before', 80), ('current_after', 96), ('target_after', 112)]},
                               'normal': struct.unpack_from('<3f', record, off + 16)})
            print(json.dumps({'physics_trace': 'update', 'sequence': sequence, 'thread': thread,
                              'dt': struct.unpack_from('<f', record, 32)[0], 'movement': args.movement,
                              'animation': args.animation, 'stages': stages, 'contacts': events,
                              'suppressed_before': bool(struct.unpack_from('<I', record, 2016)[0]),
                              'suppressed_after': bool(struct.unpack_from('<I', record, 2024)[0]),
                              'contact_overflow': struct.unpack_from('<Q', record, 56)[0]}), flush=True)
    finally:
        api.CloseHandle(handle); reader.close()


if __name__ == '__main__': main()
