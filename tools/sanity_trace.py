"""Bounded sanity metrics over SLOPE-06 events; same CLI as outlier_trace.

No native instrumentation or A+C behavior changes. E3/E4 observations are
poll-based, separate from native physical events, and are not atomic frames.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import sys
import time
from typing import cast

import outlier_trace
from runtime_read import ProcessReader
from movement_probe import resolve


Vector = tuple[float, ...]
Group = dict[str, object]
Event = dict[str, object]


class SanityHistory(outlier_trace.History):
    def __init__(self, reader: ProcessReader, state: dict[str, int]) -> None:
        super().__init__(reader, state)
        self.group_count = 0
        self.first: Group | None = None
        self.last: Group | None = None
        self.first_accepted: Group | None = None
        self.worst: list[tuple[float, Group]] = []
        self.start_position: Vector | None = None
        self.end_position: Vector | None = None
        self.first_physical_qpc: int | None = None
        self.last_physical_qpc: int | None = None
        self.path_xz = 0.0
        self.y_bounds: list[float] | None = None
        self.requested_y: list[float] | None = None
        self.first_dy: list[float] | None = None
        self.extra_dy: list[float] | None = None
        self.first_steps = self.extra_steps = self.preflight_attempts = self.preflight_hits = 0
        self.normal_bounds: dict[str, list[list[float]]] = {}
        self.windows: dict[int, Group] = {}
        self.extra_alignment: float | None = None
        self.polled_kcc = resolve(reader, int(sys.argv[2], 0))[2] if reader is not None else None

    def window(self, seconds: float) -> Group:
        key = math.floor(seconds * 4)
        if key not in self.windows:
            if len(self.windows) >= 722:
                raise ValueError('Sanity timeline exceeded the 180-second capture bound')
            self.windows[key] = {'QPC_seconds': key / 4, 'extra_steps': 0,
                                 'first_steps': 0, 'XZ_path': 0., 'E3_E4_poll': []}
        return self.windows[key]

    def poll(self) -> bool:
        stopped = super().poll()
        if not stopped and self.polled_kcc is not None:
            window = self.window(time.perf_counter())
            flags = list(self.reader.read(self.polled_kcc + 0xE3, 2))
            values = cast(list[list[int]], window['E3_E4_poll'])
            if flags not in values:
                values.append(flags)
        return stopped

    @staticmethod
    def extend(bounds: list[float] | None, value: float) -> list[float]:
        return [value, value] if bounds is None else [min(bounds[0], value), max(bounds[1], value)]

    @staticmethod
    def witness(group: Group) -> Group:
        result = {key: value for key, value in group.items() if key not in ('events', 'last_extras')}
        events = cast(list[Event], group['events'])
        result['event_count'] = len(events)
        result['events'] = events[:32]
        result['omitted_events'] = max(0, len(events) - 32)
        return deepcopy(result)

    def finish(self, group: Group) -> None:
        finished = bool(group.get('finished'))
        super().finish(group)
        if finished:
            return
        self.group_count += 1
        events = cast(list[Event], group['events'])
        has_first = any(event['stage'] == 'vanilla_physical' for event in events)
        score = 0.0
        original_requested: Vector | None = None
        for event in events:
            stage = event['stage']
            if 'ghost_before' in event:
                for point in ('ghost_before', 'ghost_after'):
                    self.y_bounds = self.extend(self.y_bounds, cast(Vector, event[point])[1])
            if stage == 'extra_preflight':
                self.preflight_attempts += 1
                hit = int(str(event['preflight_hit']), 16) != 0
                self.preflight_hits += int(hit)
                if hit:
                    self.normal('preflight_hit', cast(Vector, event['preflight_normal']))
            if stage == 'surface_segment' and cast(int, event['result']) >= 0:
                self.normal('surface_hit', cast(Vector, event['normal']))
            if stage not in ('vanilla_physical', 'extra_physical', 'physical_update'):
                continue
            # The outer physical_update includes the two inner A+C steps.
            if stage == 'physical_update' and has_first:
                continue
            before = cast(Vector, event['ghost_before'])
            after = cast(Vector, event['ghost_after'])
            requested = cast(Vector, event['requested'])
            ticks = cast(int, event['QPC'])
            if self.start_position is None:
                self.start_position, self.first_physical_qpc = before, ticks
            self.end_position, self.last_physical_qpc = after, ticks
            self.path_xz += math.hypot(after[0] - before[0], after[2] - before[2])
            self.requested_y = self.extend(self.requested_y, requested[1])
            dy = after[1] - before[1]
            window = self.window(ticks / self.state['qpc_frequency'])
            window['XZ_path'] = cast(float, window['XZ_path']) + math.hypot(
                after[0] - before[0], after[2] - before[2])
            counter = 'extra_steps' if stage == 'extra_physical' else 'first_steps'
            window[counter] = cast(int, window[counter]) + 1
            if stage == 'vanilla_physical':
                original_requested = requested
            if stage == 'extra_physical':
                window.setdefault('first_extra_QPC', ticks)
                window['last_extra_QPC'] = ticks
                if original_requested is not None:
                    length = math.hypot(*requested[::2]) * math.hypot(*original_requested[::2])
                    if length > 0:
                        alignment = (requested[0] * original_requested[0] +
                                     requested[2] * original_requested[2]) / length
                        self.extra_alignment = alignment if self.extra_alignment is None else min(
                            self.extra_alignment, alignment)
            score = max(score, abs(dy))
            if stage == 'extra_physical':
                self.extra_steps += 1
                self.extra_dy = self.extend(self.extra_dy, dy)
            else:
                self.first_steps += 1
                self.first_dy = self.extend(self.first_dy, dy)
        evidence = self.witness(group)
        if self.first_accepted is None and any(event['stage'] == 'extra_physical' for event in events):
            self.first_accepted = evidence
        if self.first is None:
            self.first = evidence
        self.last = evidence
        self.worst.append((score, evidence))
        self.worst.sort(key=lambda item: item[0], reverse=True)
        del self.worst[5:]

    def normal(self, source: str, value: Vector) -> None:
        if source not in self.normal_bounds:
            self.normal_bounds[source] = [[component, component] for component in value]
        else:
            self.normal_bounds[source] = [self.extend(bounds, component)
                                          for bounds, component in zip(self.normal_bounds[source], value)]

    def metrics(self) -> Group:
        distance = None
        if self.start_position is not None and self.end_position is not None:
            distance = math.hypot(self.end_position[0] - self.start_position[0],
                                  self.end_position[2] - self.start_position[2])
        elapsed = None
        if self.first_physical_qpc is not None and self.last_physical_qpc is not None:
            elapsed = (self.last_physical_qpc - self.first_physical_qpc) / self.state['qpc_frequency']
        return {'sanity': 'summary', 'producer_groups': self.group_count,
                'ghost_Y_bounds': self.y_bounds, 'start': self.start_position, 'end': self.end_position,
                'XZ_path': self.path_xz, 'XZ_distance': distance, 'physical_entry_elapsed_s': elapsed,
                'first_steps': self.first_steps, 'extra_steps': self.extra_steps,
                'first_step_delta_Y_bounds': self.first_dy, 'extra_step_delta_Y_bounds': self.extra_dy,
                'requested_Y_bounds': self.requested_y, 'preflight_attempts': self.preflight_attempts,
                'preflight_hits': self.preflight_hits, 'accepted_extras': self.extra_steps,
                'hit_normal_component_bounds': self.normal_bounds,
                'max_consumed_return': self.max_return, 'max_abs_integration_X': self.max_dx,
                'extra_min_XZ_alignment': self.extra_alignment,
                'physical_windows': [self.windows[key] for key in sorted(self.windows)],
                'first_producer': self.first, 'last_producer': self.last,
                'first_accepted_extra_producer': self.first_accepted,
                'worst_abs_delta_Y_producers': [{'max_abs_delta_Y': score, 'producer': group}
                                               for score, group in self.worst]}

    def output(self) -> None:
        super().output()
        print(json.dumps(self.metrics()), flush=True)


def self_check() -> None:
    history = SanityHistory(cast(ProcessReader, None), {'qpc_frequency': 1000})
    first = {'stage': 'vanilla_physical', 'QPC': 100, 'ghost_before': (0., 1., 0.),
             'ghost_after': (1., 1.2, 0.), 'requested': (1., .2, 0.)}
    extra = {'stage': 'extra_physical', 'QPC': 101, 'ghost_before': (1., 1.2, 0.),
             'ghost_after': (1.25, 1.2, 0.), 'requested': (.25, 0., 0.)}
    outer = {'stage': 'physical_update', 'QPC': 99, 'ghost_before': (0., 1., 0.),
             'ghost_after': (1.25, 1.2, 0.), 'requested': (1., .2, 0.)}
    preflight = {'stage': 'extra_preflight', 'preflight_hit': '0x0', 'preflight_normal': (0., 0., 0.)}
    group: Group = {'producer': 1, 'events': [outer, first, preflight, extra],
                    'thread': 1, 'getter_thread': 1, 'consumed_return': 4.1,
                    'integration_delta': (.7, 0., 0.), 'source': 'NORMAL_DT'}
    history.finish(group); history.finish(group)
    assert history.group_count == 1 and history.first_steps == 1 and history.extra_steps == 1
    assert history.path_xz == 1.25 and history.metrics()['XZ_distance'] == 1.25
    assert history.y_bounds == [1., 1.2] and history.requested_y == [0., .2]
    assert math.isclose(history.first_dy[1], .2) and history.extra_dy == [0., 0.]
    assert history.preflight_attempts == 1 and history.preflight_hits == 0
    assert history.first_accepted is not None and history.first_accepted['producer'] == 1
    assert history.extra_alignment == 1.0
    assert history.windows[0]['extra_steps'] == 1 and history.windows[0]['first_steps'] == 1
    assert history.windows[0]['first_extra_QPC'] == history.windows[0]['last_extra_QPC'] == 101
    assert history.producers == 1 and history.max_return == 4.1 and history.max_dx == .7
    for producer in range(2, 9):
        hit = {**preflight, 'preflight_hit': '0x123', 'preflight_normal': (-1., 0., 0.)}
        vanilla = {**first, 'stage': 'physical_update', 'QPC': producer * 100}
        history.finish({'producer': producer, 'events': [vanilla, hit]})
    assert history.group_count == 8 and len(history.worst) == 5
    assert history.preflight_hits == 7 and history.extra_steps == 1
    assert history.first_accepted['producer'] == 1
    assert history.first['producer'] == 1 and history.last['producer'] == 8
    assert history.normal_bounds['preflight_hit'] == [[-1., -1.], [0., 0.], [0., 0.]]
    assert history.metrics()['physical_entry_elapsed_s'] == .7
    assert history.witness({'events': [first] * 40})['omitted_events'] == 8
    print('sanity self-check passed')


def main() -> None:
    if sys.argv[1:] == ['self-check']:
        outlier_trace.main()
        self_check()
        return
    original = outlier_trace.History
    outlier_trace.History = SanityHistory
    try:
        outlier_trace.main()
    finally:
        outlier_trace.History = original


if __name__ == '__main__':
    main()
