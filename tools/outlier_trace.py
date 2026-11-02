"""SLOPE-06 bounded producer history; A+C implementation is reused unchanged.

Run self-check before live use. Output contains summaries and a frozen 64/1/16
producer window only on a trigger. Private pages survive until game exit.
"""
from __future__ import annotations

import argparse
import ctypes as ct
from ctypes import wintypes as wt
import json
import struct
import sys
from collections import deque

import capstone

import terrain_trace as terrain
from movement_probe import resolve
from run_perturb import animation_rate_shim, perturb_shim
from runtime_read import BASE, ProcessReader
from walk_trace import rate_shim, trace
from xref import load_image


def timing_getter() -> bytes:
    """Record the branch and the single source read actually returned in XMM0."""
    code = bytearray()
    labels: dict[str, int] = {}
    jumps: list[tuple[int, str]] = []
    def emit(raw: str) -> None: code.extend(bytes.fromhex(raw))
    def address(value: int) -> None:
        emit('49 BB'); code.extend(struct.pack('<Q', BASE + value))
    def jump(op: str, label: str) -> None:
        emit(op); jumps.append((len(code), label)); code.extend(b'\0' * 4)
    address(0xC82FAC); emit('41 0F B6 03')
    emit('4D 85 ED'); jump('0F 84', 'select')
    emit('41 89 85 DC 01 00 00')
    address(0xA63248); emit('41 8B 13 41 89 95 E0 01 00 00')
    address(0x803C3C); emit('41 8B 13 41 89 95 E4 01 00 00')
    labels['select'] = len(code)
    emit('83 F8 01'); jump('0F 85', 'normal')
    address(0xA63248); emit('F3 41 0F 10 03')
    emit('4D 85 ED'); jump('0F 84', 'multiply')
    emit('41 C7 85 D8 01 00 00 02 00 00 00 F3 41 0F 11 85 E8 01 00 00')
    emit('F3 41 0F 11 85 E0 01 00 00')
    labels['multiply'] = len(code)
    address(0x803C3C); emit('F3 41 0F 59 03 C3')
    labels['normal'] = len(code)
    address(0xA63240); emit('F3 41 0F 10 03')
    emit('4D 85 ED'); jump('0F 84', 'return')
    emit('41 C7 85 D8 01 00 00 01 00 00 00 F3 41 0F 11 85 E8 01 00 00')
    emit('F3 41 0F 11 85 A8 01 00 00')
    labels['return'] = len(code); emit('C3')
    for offset, label in jumps:
        struct.pack_into('<i', code, offset, labels[label] - offset - 4)
    return bytes(code)


class History:
    def __init__(self, reader: ProcessReader, state: dict[str, int]) -> None:
        self.reader, self.state = reader, state
        self.cursor = 0
        self.groups: deque[dict[str, object]] = deque(maxlen=82)
        self.trigger: int | None = None
        self.frozen = False
        self.producers = 0
        self.max_return = self.max_dx = 0.0
        self.max_y = -float('inf')
        self.last_qpc: int | None = None
        self.intervals: list[float] = []
        self.sources: dict[str, int] = {}
        self.last_extras: deque[dict[str, object]] = deque(maxlen=8)
        self.extra_count = self.preflight_count = 0
        self.start: tuple[float, ...] | None = None
        self.ghost: tuple[float, ...] | None = None
        self.first_direction: tuple[float, ...] | None = None

    def finish(self, group: dict[str, object]) -> None:
        if group.get('finished'): return
        group['finished'] = True
        if 'consumed_return' not in group or 'integration_delta' not in group: return
        if group['thread'] != group['getter_thread']:
            raise ValueError('Getter/producer thread mismatch; discard capture')
        self.producers += 1
        returned = float(group['consumed_return'])
        dx = abs(group['integration_delta'][0])
        self.max_return = max(self.max_return, returned)
        self.max_dx = max(self.max_dx, dx)
        source = str(group['source'])
        self.sources[source] = self.sources.get(source, 0) + 1
        if (returned > 6 or dx > 1) and self.trigger is None:
            self.trigger = int(group['producer'])
            print(json.dumps({'outlier': 'trigger', 'producer': self.trigger,
                              'return': returned, 'abs_delta_X': dx}), flush=True)

    def poll(self) -> bool:
        if self.frozen: return True
        count = struct.unpack('<Q', self.reader.read(self.state['header'], 8))[0]
        if count - self.cursor > terrain.CAPACITY:
            raise ValueError('Observer fell behind native ring; discard capture')
        while self.cursor < count:
            slot = self.cursor & (terrain.CAPACITY - 1)
            raw = self.reader.read(self.state['records'] + slot * terrain.STRIDE, terrain.STRIDE)
            sequence, thread, complete, stage, caller, producer = struct.unpack_from('<6Q', raw)
            if sequence != self.cursor + 1 or complete != sequence: break
            self.cursor += 1
            if stage not in terrain.STAGES: raise ValueError('Invalid stage')
            if not self.groups or producer != self.groups[-1]['producer']:
                if self.groups:
                    if producer < self.groups[-1]['producer']:
                        raise ValueError('Cross-producer reordering; discard capture')
                    self.finish(self.groups[-1])
                if self.trigger is not None and producer > self.trigger + 16:
                    self.frozen = True
                    return True
                self.groups.append({'producer': producer, 'events': [],
                                    'last_extras': list(self.last_extras)})
            group = self.groups[-1]
            ticks, ok = struct.unpack_from('<2Q', raw, 48)
            if not ok: raise ValueError('Native QPC failed')
            event: dict[str, object] = {'sequence': sequence, 'thread': thread,
                                      'stage': terrain.STAGES[stage], 'QPC': ticks,
                                      'caller': hex(caller)}
            vector = lambda offset: struct.unpack_from('<4f', raw, offset)[:3]
            if stage == 1 and self.start is None:
                self.start = self.ghost
            if stage == 2:
                group['QPC'] = ticks
                group['interval'] = ((ticks - self.last_qpc) / self.state['qpc_frequency']
                                     if self.last_qpc is not None else None)
                self.last_qpc = ticks
                if group['interval'] is not None: self.intervals.append(group['interval'])
            if stage == 2:
                group.update(thread=thread, parameter=struct.unpack_from('<f', raw, 160)[0],
                             current=vector(96), target=vector(144), requested_before=vector(128),
                             requested_after=vector(224), flags=list(raw[168:173]),
                             timing=dict(zip(('A63238', 'A6323C', 'A63240', 'A63244'),
                                             struct.unpack_from('<4f', raw, 416))),
                             player_9FE8=struct.unpack_from('<f', raw, 432)[0],
                             player_9F2C=struct.unpack_from('<f', raw, 440)[0], player_4E0=raw[464],
                             target_current=[a-b for a,b in zip(vector(144), vector(96))],
                             integration_before=vector(112), integration_after=vector(208),
                             integration_delta=[a-b for a,b in zip(vector(208), vector(112))])
            if stage == 12:
                branch, flag, fixed_dt, constant, selected = struct.unpack_from('<II3f', raw, 472)
                group.update(consumed_return=struct.unpack_from('<f', raw, 448)[0],
                             source={1: 'NORMAL_DT', 2: 'FIXED_ALTERNATE'}.get(branch, 'OTHER'),
                             getter_thread=thread, getter_sequence=sequence,
                             getter_QPC=ticks, C82FAC=flag, A63248=fixed_dt,
                             alternate_constant=constant, selected_value=selected,
                             timing=dict(zip(('A63238', 'A6323C', 'A63240', 'A63244'),
                                             struct.unpack_from('<4f', raw, 416))),
                             player_9FE8=struct.unpack_from('<f', raw, 432)[0],
                             player_9F2C=struct.unpack_from('<f', raw, 440)[0], player_4E0=raw[464])
            if stage == 14:
                group['normalized_direction'] = vector(304)
                if self.first_direction is None: self.first_direction = vector(304)
            if stage in (7, 10, 11, 15, 16):
                event.update(ghost_before=vector(288), ghost_after=vector(304),
                             requested=vector(320), C0_before=raw[672], C0_after=raw[928],
                             D0_before=vector(688), D0_after=vector(944))
                self.max_y = max(self.max_y, vector(288)[1], vector(304)[1])
                self.ghost = vector(304)
                if stage == 11:
                    self.extra_count += 1
                    event['second_wrapper'] = True
                    event['extra_displacement'] = [a-b for a,b in zip(vector(304), vector(288))]
                    event['preflight'] = next((e for e in reversed(group['events'])
                                               if e['stage'] == 'extra_preflight' and e['thread'] == thread), None)
                    self.last_extras.append({'producer': producer, **event})
            if stage == 5:
                event.update(query_from=vector(288), query_to=vector(304),
                             hit=vector(336), normal=vector(352), result=struct.unpack_from('<i', raw, 368)[0])
            if stage == 13:
                self.preflight_count += 1
                event.update(extra_from=vector(288), extra_to=vector(304),
                             preflight_hit=hex(struct.unpack_from('<Q', raw, 384)[0]),
                             preflight_normal=vector(352), preflight_fraction=struct.unpack_from('<f', raw, 392)[0])
            group['events'].append(event)
        return False

    def output(self) -> None:
        self.poll()
        if self.groups: self.finish(self.groups[-1])
        print(json.dumps({'outlier': 'summary', 'producers': self.producers,
                          'events': self.cursor, 'max_consumed_return': self.max_return,
                          'max_abs_integration_X': self.max_dx, 'max_ghost_Y': self.max_y,
                          'QPC_interval_range': [min(self.intervals), max(self.intervals)] if self.intervals else None,
                          'sources': self.sources, 'trigger': self.trigger, 'frozen': self.frozen}), flush=True)
        print(json.dumps({'outlier': 'lane', 'start': self.start, 'first_normalized_direction': self.first_direction,
                          'accepted_extras': self.extra_count, 'preflights': self.preflight_count}), flush=True)
        if self.trigger is not None:
            window = [g for g in self.groups if self.trigger - 64 <= g['producer'] <= self.trigger + 16]
            print(json.dumps({'outlier': 'window', 'prehistory': sum(g['producer'] < self.trigger for g in window),
                              'posthistory': sum(g['producer'] > self.trigger for g in window), 'producers': window}), flush=True)


def main() -> None:
    if sys.argv[1:] == ['self-check']:
        terrain.self_check()
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
        for code in [timing_getter(), terrain.event_shim(1, 2, 3, 4, 5, 12, rolling=True)]:
            instructions = list(md.disasm(code, 0)); starts = {i.address for i in instructions}
            assert sum(i.size for i in instructions) == len(code)
            assert all(i.operands[0].imm in starts for i in instructions if i.group(capstone.CS_GRP_JUMP))
        class FakeReader:
            def read(self, address: int, size: int) -> bytes:
                if address == 1: return struct.pack('<Q', published_count)
                return events[(address - 1024) // 1024]
        events: list[bytes] = []
        for producer in range(1, 101):
            for stage in (1, 2, 12):
                raw = bytearray(1024)
                sequence = len(events) + 1
                struct.pack_into('<8Q', raw, 0, sequence, 7, sequence, stage, 0, producer, producer * 100, 1)
                if stage == 2: struct.pack_into('<f', raw, 208, 2.625 if producer == 70 else .7)
                if stage == 12:
                    struct.pack_into('<f', raw, 448, 4)
                    struct.pack_into('<I', raw, 472, 1)
                events.append(bytes(raw))
        published_count = len(events)
        history = History(FakeReader(), {'header': 1, 'records': 1024, 'qpc_frequency': 1000})
        assert history.poll() and history.trigger == 70 and history.frozen
        window = [g for g in history.groups if 6 <= g['producer'] <= 86]
        assert len(window) == 81 and history.max_dx == 2.625
        for index, event in enumerate(events):
            raw = bytearray(event)
            if index % 3 == 1: struct.pack_into('<f', raw, 208, .7)
            if index == (70 - 1) * 3 + 2: struct.pack_into('<f', raw, 448, 7)
            events[index] = bytes(raw)
        history = History(FakeReader(), {'header': 1, 'records': 1024, 'qpc_frequency': 1000})
        assert history.poll() and history.trigger == 70 and history.max_return == 7
        wrapped = [bytes(1024)] * terrain.CAPACITY
        for index in range(30):
            raw = bytearray(events[index]); sequence = terrain.CAPACITY + index + 1
            struct.pack_into('<Q', raw, 0, sequence); struct.pack_into('<Q', raw, 16, sequence)
            wrapped[(sequence - 1) & (terrain.CAPACITY - 1)] = bytes(raw)
        events = wrapped; published_count = terrain.CAPACITY + 30
        history = History(FakeReader(), {'header': 1, 'records': 1024, 'qpc_frequency': 1000})
        history.cursor = terrain.CAPACITY
        assert not history.poll() and history.cursor == published_count
        print('outlier self-check passed'); return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid', type=int); parser.add_argument('pc', type=lambda v: int(v, 0))
    parser.add_argument('condition', choices=('V', 'D', 'A'))
    parser.add_argument('seconds', type=float)
    args = parser.parse_args()
    if not 0 < args.seconds <= 180: parser.error('Bounded capture requires 0..180 seconds')
    reader = ProcessReader(args.pid); api = reader.api
    api.VirtualAllocEx.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_size_t, wt.DWORD, wt.DWORD]
    api.VirtualAllocEx.restype = ct.c_void_p
    api.WriteProcessMemory.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.POINTER(ct.c_size_t)]
    api.WriteProcessMemory.restype = wt.BOOL
    api.FlushInstructionCache.argtypes = [wt.HANDLE, ct.c_void_p, ct.c_size_t]; api.FlushInstructionCache.restype = wt.BOOL
    identity = resolve(reader, args.pc); kcc = identity[2]
    handle = api.OpenProcess(0x438, False, args.pid)
    if not handle: raise ct.WinError(ct.get_last_error())
    original_builder = terrain.event_shim
    def rolling(header: int, records: int, pc: int, controller: int,
                original: int, stage: int, qpc: int = 0) -> bytes:
        if stage == 12: original = header - 0x10000 + 0x1A000
        return original_builder(header, records, pc, controller, original, stage, qpc,
                                rolling=True, producer_stage=2)
    try:
        image = load_image()
        if reader.read(BASE + 0x69B4C0, 0x23) != image.pe.get_data(0x69B4C0, 0x23):
            raise ValueError('Getter differs from verified executable')
        if struct.unpack('<f', reader.read(BASE + 0x803C3C, 4))[0] != 60:
            raise ValueError('Unexpected alternate timing constant')
        terrain.event_shim = rolling
        state = terrain.setup(reader, handle, args.pc, kcc, args.condition != 'V', 0x3E2D712B, args.condition == 'D')
        terrain.event_shim = original_builder
        code = timing_getter(); written = ct.c_size_t(); buffer = ct.create_string_buffer(code)
        if not api.WriteProcessMemory(handle, state['page'] + 0x1A000, buffer, len(code), ct.byref(written)) or written.value != len(code):
            raise ct.WinError(ct.get_last_error())
        if not api.FlushInstructionCache(handle, state['page'], 0x1B000): raise ct.WinError(ct.get_last_error())
        history = History(reader, state)
        owner = struct.unpack('<Q', reader.read(args.pc + 0x4C0, 8))[0]
        controller = struct.unpack('<Q', reader.read(owner + 0x108, 8))[0]
        channel = struct.unpack('<Q', reader.read(controller + 0x2F0, 8))[0]
        def animation(log: int, original: int) -> bytes:
            return animation_rate_shim(log, original, args.pc, identity[0], owner, controller, channel,
                                       1, 1.25, 0x3E2D712B, state['header'] + 24)
        def production(log: int, original: int) -> bytes:
            prefix = bytes.fromhex('50 41 52 49 BA') + struct.pack('<Q', state['header'] + 16)
            prefix += bytes.fromhex('66 0F 7E D0 41 89 02 41 5A 58')
            return prefix + perturb_shim(log, state['page'] + 0x8000, args.pc, identity[0], 1, 0x3E2D712B)
        print(json.dumps({'outlier': 'setup', 'condition': args.condition, **state}), flush=True)
        trace(reader, args.pid, args.pc, args.seconds, production,
              animation if args.condition != 'V' else rate_shim,
              {0x08: state['page'] + 0xB000, 0x18: state['page'] + 0xD000,
               0x38: state['page'] + 0x18000, 0x60: state['page'] + 0x19000},
              {0x168: state['page'], 0x170: state['page'] + 0xA000, 0x178: state['page'] + 0x5000}, history.poll)
        history.output()
    finally:
        terrain.event_shim = original_builder
        api.CloseHandle(handle); reader.close()


if __name__ == '__main__': main()
