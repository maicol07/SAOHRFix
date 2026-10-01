"""Temporary Xbox pad on the existing ViGEmBus. JSON commands on stdin.

Example: {"x":0,"y":0.25,"seconds":3,"buttons":0}
Only virtual input is written. Every command ends at neutral, including failures.
Closing stdin disconnects the device. No driver installation or game patch.
"""

from __future__ import annotations

import json
import math
import sys
import time

import vgamepad as vg


def axis(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Axis must be a number")
    if not math.isfinite(value) or not -1 <= value <= 1:
        raise ValueError("Axis must be finite and within -1..1")
    return round(value * 32767)


def pulse(pad: vg.VX360Gamepad, command: dict[str, object]) -> None:
    if set(command) != {"x", "y", "seconds", "buttons"}:
        raise ValueError("Expected exactly x, y, seconds, buttons")
    x, y = axis(command["x"]), axis(command["y"])
    seconds, buttons = command["seconds"], command["buttons"]
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ValueError("seconds must be a number")
    if not math.isfinite(seconds) or not 0 < seconds <= 15:
        raise ValueError("seconds must be finite and within 0..15")
    if isinstance(buttons, bool) or not isinstance(buttons, int) or not 0 <= buttons <= 65535:
        raise ValueError("buttons must be an integer within 0..65535")
    try:
        pad.left_joystick(x_value=x, y_value=y)
        pad.report.wButtons = buttons
        pad.update()
        print(json.dumps({"status": "active", "x": x, "y": y,
                          "seconds": seconds, "time_ns": time.monotonic_ns()}), flush=True)
        time.sleep(seconds)
    finally:
        pad.reset()
        pad.update()
    print(json.dumps({"status": "neutral", "time_ns": time.monotonic_ns()}), flush=True)


def self_check() -> None:
    assert [axis(v) for v in (-1, 0, 0.25, 1)] == [-32767, 0, 8192, 32767]
    for value in (True, "0", math.nan, math.inf, 1.01):
        try:
            axis(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid axis accepted: {value!r}")
    print("self-check passed")


def main() -> None:
    if sys.argv[1:] == ["self-check"]:
        self_check()
        return
    if sys.argv[1:]:
        raise ValueError("Usage: virtual_pad.py [self-check]")
    pad = vg.VX360Gamepad()
    try:
        print(json.dumps({"status": "connected", "index": pad.get_index()}), flush=True)
        for line in sys.stdin:
            command = json.loads(line)
            if not isinstance(command, dict):
                raise ValueError("Expected a JSON object")
            pulse(pad, command)
    finally:
        pad.reset()
        pad.update()


if __name__ == "__main__":
    main()
