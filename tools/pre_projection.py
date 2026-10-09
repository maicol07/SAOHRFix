"""Player-instance diagnostic forward step copies; original image stays intact.

Used by slope_trace --pre-projection. No collision-response replacement.
Private pages remain until game exit, including after restored vptrs.
"""
from __future__ import annotations

import ctypes as ct
import json
import math
import struct
import sys

import capstone

from runtime_read import BASE, MemoryRegion, ProcessReader

CAPACITY = 4096
STRIDE = 256
STEP = 0x729EF0
FORWARD = 0x72A9D0


def relocate(data: bytes, source: int, target: int, calls: dict[int, int]) -> bytes:
    """Relocate two verified complete functions; reject unsupported encodings."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    instructions = list(md.disasm(data, source))
    if sum(i.size for i in instructions) != len(data) or instructions[-1].mnemonic != 'ret':
        raise ValueError('Incomplete verified function')
    result = bytearray(data)
    for i in instructions:
        pos = i.address - source
        for operand in i.operands:
            if operand.type == capstone.CS_OP_MEM and operand.mem.base == capstone.x86.X86_REG_RIP:
                absolute = i.address + i.size + operand.mem.disp
                struct.pack_into('<i', result, pos + i.disp_offset, absolute - (target + pos + i.size))
        if i.group(capstone.CS_GRP_JUMP) or i.group(capstone.CS_GRP_CALL):
            if i.operands[0].type != capstone.CS_OP_IMM:
                continue
            absolute = i.operands[0].imm
            destination = calls.get(i.address, absolute)
            if i.address not in calls and source <= absolute < source + len(data):
                destination = target + absolute - source
            if i.imm_size not in (1, 4):
                raise ValueError('Unsupported branch relocation')
            struct.pack_into('<b' if i.imm_size == 1 else '<i', result,
                             pos + i.imm_offset, destination - (target + pos + i.size))
    return bytes(result)


def projection_shim(page: int, trace_page: int, pc: int, kcc: int,
                    movement: float, baseline_bits: int, channel: int, physics_id: int,
                    records: int) -> bytes:
    code = bytearray.fromhex('41 54 41 55 41 56 41 57 48 81 EC D8 00 00 00')
    labels: dict[str, int] = {}
    jumps: list[tuple[int, str]] = []

    def emit(hex_bytes: str) -> None:
        code.extend(bytes.fromhex(hex_bytes))

    def imm(op: str, value: int) -> None:
        emit(op); code.extend(struct.pack('<Q', value))

    def jump(op: str, label: str) -> None:
        emit(op); jumps.append((len(code), label)); code.extend(b'\0' * 4)

    def copy(src: str, offset: int, destination: int) -> None:
        emit(src); code.extend(struct.pack('<i', offset))
        emit('49 89 85'); code.extend(struct.pack('<i', destination))

    for reg in range(6):
        emit(f'F3 0F 7F {0x84 + 8 * reg:02X} 24'); code.extend(struct.pack('<i', 0x40 + reg * 16))
    for op, offset in [('48 89 8C 24', 0xA0), ('48 89 94 24', 0xA8),
                       ('4C 89 84 24', 0xB0), ('4C 89 8C 24', 0xB8)]:
        emit(op); code.extend(struct.pack('<i', offset))
    emit('49 89 CE 45 31 ED')  # r14=KCC, r13=nullable event
    imm('48 B8', kcc); emit('48 39 C1'); jump('0F 85', 'call')
    # Only this copied forward hit call, never recovery projection at AB3C.
    imm('48 B8', page + 0x2000 + 0x72ACCD - FORWARD)
    emit('48 39 84 24 F8 00 00 00'); jump('0F 85', 'call')
    imm('49 BC', page + 0x8000)
    emit('B8 01 00 00 00 F0 49 0F C1 04 24 48 3D'); code.extend(struct.pack('<I', CAPACITY))
    jump('0F 83', 'overflow')
    emit('48 C1 E0 08'); imm('49 BD', records); emit('49 01 C5')
    # Same physics update context; no assumed cross-thread producer atomicity.
    emit('65 48 8B 04 25 48 00 00 00 49 89 45 08 25 FF 00 00 00 48 C1 E0 04')
    imm('49 BA', trace_page + 0x5000); emit('4C 01 D0 4C 8B 38 4D 85 FF'); jump('0F 84', 'invalid')
    emit('65 48 8B 04 25 48 00 00 00 49 3B 47 08'); jump('0F 85', 'invalid')
    copy('49 8B 87', 0, 0)
    emit('4D 89 75 10')
    emit('48 8B 45 A0 49 89 45 20')  # original forward hit object at rbp-60
    for source, destination in [(0x70, 64), (0x90, 80)]:
        for j in (0, 8): copy('49 8B 86', source + j, destination + j)
    emit('4C 8B 9C 24 A8 00 00 00')
    for j in (0, 8): copy('49 8B 83', j, 96 + j)
    # Original forward rsp+58 is entry rsp+60, then wrapper stack +F8.
    emit('8B 84 24 58 01 00 00 41 89 85 D0 00 00 00')
    emit('41 8B 46 38 41 89 85 D4 00 00 00')
    imm('49 BA', trace_page + 0x4018)
    copy('49 8B 82', 0, 40)
    emit('0F 10 81 90 00 00 00 0F 5C 41 70 41 0F 11 45 70 41 0F 11 85 80 00 00 00')
    emit('41 0F 11 85 A0 00 00 00')  # default passed/vanilla=incoming, extra=0
    emit('0F 57 C9 41 0F 11 8D 90 00 00 00')
    # Native up-axis index must be Y; compare exactly as native closest callback.
    emit('41 83 BE E8 00 00 00 01'); jump('0F 85', 'invalid')
    emit('F3 41 0F 10 4D 64 F3 41 0F 11 8D DC 00 00 00')
    emit('F3 0F 10 51 38 0F 2F D1'); jump('0F 86', 'walkable')
    emit('41 C7 85 E4 00 00 00 00 00 00 00'); jump('E9', 'dot')
    labels['walkable'] = len(code)
    emit('41 C7 85 E4 00 00 00 01 00 00 00')
    labels['dot'] = len(code)
    emit('41 0F 10 4D 60 0F 59 C8 0F 28 D1 0F C6 D2 55 F3 0F 58 CA 0F 28 D0')
    emit('41 0F 10 5D 60 0F 59 D3 0F C6 D2 AA F3 0F 58 CA')
    emit('F3 41 0F 11 8D D8 00 00 00')
    # Log eligibility independently of the geometric decision.
    imm('49 BB', pc)
    emit('41 8B 83 24 9F 00 00 41 89 85 E8 00 00 00')
    emit('41 C7 85 EC 00 00 00'); code.extend(struct.pack('<f', movement))
    for offset, value in [(0xF8A6, 1), (0xF8AD, 0), (0xA9E9, 0xFF), (0xA9F0, 0xFE)]:
        emit('41 80 BB'); code.extend(struct.pack('<iB', offset, value)); jump('0F 85', 'call')
    emit('41 81 BB CC 9F 00 00'); code.extend(struct.pack('<i', physics_id)); jump('0F 85', 'call')
    # Channel still belongs to this player's current owner/controller.
    emit('49 8B 83 C0 04 00 00 48 8B 80 08 01 00 00 48 8B 80 F0 02 00 00')
    imm('49 BA', channel); emit('4C 39 D0'); jump('0F 85', 'call')
    emit('8B 90 14 01 00 00 85 D2'); jump('0F 88', 'call')
    emit('3B 90 B8 00 00 00'); jump('0F 8D', 'call')
    emit('4C 8B 90 A8 00 00 00 4D 85 D2'); jump('0F 84', 'call')
    emit('48 6B D2 28 41 81 7C 12 18 7A 00 00 00'); jump('0F 85', 'call')
    emit('41 C7 45 38 01 00 00 00')
    if movement == 1:
        jump('E9', 'call')  # Vanilla control only records; no latch or target writes.
    emit('41 83 BD E4 00 00 00 00'); jump('0F 85', 'call')
    emit('0F 57 D2 0F 2F D1'); jump('0F 86', 'call')  # dot<0, NaN rejects
    emit('B8 00 00 80 3F 66 0F 6E D0 41 0F 2F 95 D0 00 00 00'); jump('0F 86', 'call')
    # Qualifying non-walkable contact keeps future suppression active.
    emit('41 C7 44 24 10 01 00 00 00')
    imm('49 BA', trace_page + 0x4018); emit('B8 01 00 00 00 41 87 02')
    # De-scale only once in this physical update, while actual run value is boosted.
    baseline = struct.unpack('<f', struct.pack('<I', baseline_bits))[0]
    emit('41 81 BB 24 9F 00 00'); code.extend(struct.pack('<f', baseline * movement)); jump('0F 85', 'call')
    emit('49 8B 47 00 49 3B 44 24 08'); jump('0F 84', 'call')
    emit('49 89 44 24 08')
    emit('B8'); code.extend(struct.pack('<f', movement)); emit('66 0F 6E C8 0F C6 C9 00')
    emit('0F 5E C1 41 0F 11 85 80 00 00 00 41 0F 11 85 A0 00 00 00')
    emit('41 0F 10 4D 70 0F 5C C8 41 0F 11 8D 90 00 00 00')
    emit('41 0F 58 46 70 41 0F 11 86 90 00 00 00')
    emit('41 0F 10 86 90 00 00 00 41 0F 5C 46 70 41 0F 11 85 A0 00 00 00')
    emit('41 C7 85 E0 00 00 00 01 00 00 00'); jump('E9', 'call')
    labels['overflow'] = len(code); emit('F0 49 FF 44 24 18'); jump('E9', 'unrecorded')
    labels['invalid'] = len(code); emit('F0 49 FF 44 24 20')
    labels['unrecorded'] = len(code); emit('45 31 ED')
    labels['call'] = len(code)
    for op, offset in [('48 8B 8C 24', 0xA0), ('48 8B 94 24', 0xA8),
                       ('4C 8B 84 24', 0xB0), ('4C 8B 8C 24', 0xB8)]:
        emit(op); code.extend(struct.pack('<i', offset))
    for reg in range(6):
        emit(f'F3 0F 6F {0x84 + 8 * reg:02X} 24'); code.extend(struct.pack('<i', 0x40 + reg * 16))
    imm('48 B8', BASE + 0x72B3C0); emit('FF D0 48 89 84 24 C0 00 00 00 F3 0F 7F 44 24 40')
    emit('4D 85 ED'); jump('0F 84', 'return')
    for j in (0, 8): copy('49 8B 86', 0x90 + j, 176 + j)
    emit('41 0F 10 86 90 00 00 00 41 0F 5C 46 70 41 0F 11 85 C0 00 00 00')
    imm('49 BA', trace_page + 0x4018); copy('49 8B 82', 0, 48)
    emit('49 8B 45 00 49 89 45 18')  # publish update sequence
    labels['return'] = len(code)
    emit('48 8B 84 24 C0 00 00 00 F3 0F 6F 44 24 40 48 81 C4 D8 00 00 00')
    emit('41 5F 41 5E 41 5D 41 5C C3')
    for offset, label in jumps: struct.pack_into('<i', code, offset, labels[label] - offset - 4)
    return bytes(code)


def forward_wrapper(page: int, trace_page: int) -> bytes:
    """Release on forward pass with no qualifying inward steep hit, not a timer."""
    # Keep original RCX/RDX/R8 and SIMD args; only volatile RAX/R10 used pre-call.
    code = bytearray.fromhex('48 83 EC 28 49 BA') + struct.pack('<Q', page + 0x8000)
    code.extend(bytes.fromhex('41 C7 42 10 00 00 00 00 48 B8') + struct.pack('<Q', page + 0x2000))
    code.extend(bytes.fromhex('FF D0 48 89 44 24 20 49 BA') + struct.pack('<Q', page + 0x8000))
    code.extend(bytes.fromhex('41 83 7A 10 00 75 0F 49 BA') + struct.pack('<Q', trace_page + 0x4018))
    code.extend(bytes.fromhex('31 C0 41 87 02 48 8B 44 24 20 48 83 C4 28 C3'))
    return bytes(code)


def prepare(reader: ProcessReader, handle: int, trace_page: int, pc: int,
            kcc: int, movement: float, baseline_bits: int) -> dict[str, int]:
    if movement not in (1, 1.15, 1.25):
        raise ValueError('Only vanilla/1.15/1.25 pre-projection diagnostics')
    up, angle, cosine = struct.unpack('<i2f', reader.read(kcc + 0xE8, 4) + reader.read(kcc + 0x34, 8))
    if up != 1 or not math.isclose(cosine, math.cos(angle), abs_tol=1e-6):
        raise ValueError('Native Y-up slope pair not verified')
    api = reader.api
    page = 0
    region = MemoryRegion()
    address = BASE - 0x70000000
    while address < BASE + 0x70000000 and api.VirtualQueryEx(
            handle, address, ct.byref(region), ct.sizeof(region)):
        start = region.base or 0
        end = start + region.size
        if end <= address: raise ValueError('Non-progressing private allocation search')
        aligned = (start + 0xFFFF) & ~0xFFFF
        if region.state == 0x10000 and end - aligned >= 0x10000:
            page = api.VirtualAllocEx(handle, aligned, 0x10000, 0x3000, 0x40)
            if page: break
        address = end
    if not page: raise OSError('No free bounded near-image code region')
    records = api.VirtualAllocEx(handle, None, CAPACITY * STRIDE, 0x3000, 4)
    if not records: raise ct.WinError(ct.get_last_error())
    owner = struct.unpack('<Q', reader.read(pc + 0x4C0, 8))[0]
    controller = struct.unpack('<Q', reader.read(owner + 0x108, 8))[0]
    channel = struct.unpack('<Q', reader.read(controller + 0x2F0, 8))[0]
    step = relocate(reader.read(BASE + STEP, 0x266), BASE + STEP, page + 0x1000,
                    {BASE + 0x72A101: page + 0x5000})
    forward = relocate(reader.read(BASE + FORWARD, 0x4A9), BASE + FORWARD, page + 0x2000,
                       {BASE + 0x72ACC8: page + 0x3000})
    physics_id = struct.unpack('<i', reader.read(pc + 0x9FCC, 4))[0]
    shim = projection_shim(page, trace_page, pc, kcc, movement, baseline_bits, channel, physics_id, records)
    for address, data in [(page + 0x1000, step), (page + 0x2000, forward),
                          (page + 0x3000, shim), (page + 0x5000, forward_wrapper(page, trace_page)),
                          (page + 0x8028, struct.pack('<Q', records))]:
        count = ct.c_size_t(); buffer = ct.create_string_buffer(data)
        if not api.WriteProcessMemory(handle, address, buffer, len(data), ct.byref(count)) or count.value != len(data):
            raise ct.WinError(ct.get_last_error())
    if not api.FlushInstructionCache(handle, page, 0x6000): raise ct.WinError(ct.get_last_error())
    print(json.dumps({'pre_projection': 'setup', 'up_axis': up, 'slope_angle': angle,
                      'slope_cosine': cosine, 'page': hex(page)}), flush=True)
    return {'page': page, 'step': page + 0x1000}


def dump(reader: ProcessReader, page: int) -> None:
    count, _, _, overflow, invalid = struct.unpack('<5Q', reader.read(page + 0x8000, 40))
    records = struct.unpack('<Q', reader.read(page + 0x8028, 8))[0]
    if count > CAPACITY or overflow or invalid:
        raise ValueError('Pre-projection capture overflow/invalid update context')
    for index in range(count):
        raw = reader.read(records + index * STRIDE, STRIDE)
        sequence, thread, kcc, complete = struct.unpack_from('<4Q', raw)
        if not sequence or sequence != complete: continue
        fields = {name: struct.unpack_from('<4f', raw, offset) for name, offset in
                  [('current', 64), ('target_before', 80), ('normal', 96), ('incoming', 112),
                   ('vanilla_equivalent', 128), ('sprint_extra', 144), ('passed', 160),
                   ('target_after', 176), ('projected', 192)]}
        print(json.dumps({'pre_projection': 'event', 'sequence': sequence, 'thread': thread,
                          'kcc': hex(kcc), 'latch_before': bool(struct.unpack_from('<I', raw, 40)[0]),
                          'hit_object': hex(struct.unpack_from('<Q', raw, 32)[0]),
                          'run_value': struct.unpack_from('<f', raw, 232)[0],
                          'configured_movement': struct.unpack_from('<f', raw, 236)[0],
                          'vanilla_method': 'incoming/factor when applied; otherwise incoming',
                          'latch_after': bool(struct.unpack_from('<I', raw, 48)[0]),
                          'run_eligible': bool(struct.unpack_from('<I', raw, 56)[0]),
                          'hit_fraction': struct.unpack_from('<f', raw, 208)[0],
                          'native_cosine': struct.unpack_from('<f', raw, 212)[0],
                          'dot': struct.unpack_from('<f', raw, 216)[0],
                          'up_dot_normal': struct.unpack_from('<f', raw, 220)[0],
                          'applied': bool(struct.unpack_from('<I', raw, 224)[0]),
                          'walkable': bool(struct.unpack_from('<I', raw, 228)[0]), **fields}), flush=True)
    print(json.dumps({'pre_projection': 'summary', 'events': count,
                      'overflow': overflow, 'invalid': invalid}), flush=True)


def self_check() -> None:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
    for code in [projection_shim(BASE + 0x2000000, 0x20000000, 0x2136E890,
                                 0x33000000, 1.15, 0x3E2D712B, 0x25000000, 8, 0x27000000),
                 forward_wrapper(BASE + 0x2000000, 0x20000000)]:
        decoded = list(md.disasm(code, 0)); boundaries = {i.address for i in decoded}
        assert sum(i.size for i in decoded) == len(code) < 4096
        assert all(i.operands[0].imm in boundaries for i in decoded if i.group(capstone.CS_GRP_JUMP))
        assert decoded[-1].mnemonic == 'ret'
    original = bytes.fromhex('48 8B 05 01 00 00 00 E8 00 00 00 00 EB 00 C3')
    relocated = relocate(original, 0x1000, 0x2000, {0x1007: 0x4000})
    decoded = list(md.disasm(relocated, 0x2000))
    assert decoded[0].address + decoded[0].size + decoded[0].disp == 0x1008
    assert decoded[1].operands[0].imm == 0x4000 and decoded[2].operands[0].imm == 0x200E
    v = (-0.589489102, -0.0000349805, 0.0036315923); factor = 1.15
    vanilla = tuple(x / factor for x in v); extra = tuple(a - b for a, b in zip(v, vanilla))
    assert all(math.isclose(a, b + c, abs_tol=1e-9) for a, b, c in zip(v, vanilla, extra))
    print('self-check passed')


if __name__ == '__main__':
    if sys.argv[1:] != ['self-check']: raise SystemExit('Use slope_trace.py --pre-projection')
    self_check()
