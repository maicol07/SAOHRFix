"""Temporary NVIDIA per-application FPS cap. No injection or game time writes.

Reads FPS integers from stdin, restores the original profile value on EOF.
Only uses an existing sao_hr.exe profile. Source: NVIDIA/nvapi headers.
"""

from __future__ import annotations

import ctypes as ct
import json
import sys
from collections.abc import Callable


U32 = ct.c_uint32
HANDLE = ct.c_void_p
FPS_ID = 0x10835002
GAME = r"W:\SteamLibrary\steamapps\common\SAOHR\sao_hr.exe"


class Value(ct.Union):
    _pack_ = 4
    _fields_ = [("number", U32), ("storage", ct.c_byte * 4100)]


class Setting(ct.Structure):
    _pack_ = 4
    _fields_ = [("version", U32), ("name", ct.c_wchar * 2048),
                ("setting_id", U32), ("kind", U32), ("location", U32),
                ("predefined", U32), ("predefined_valid", U32),
                ("default", Value), ("current", Value)]


class Application(ct.Structure):
    _fields_ = [("version", U32), ("predefined", U32),
                ("name", ct.c_wchar * 2048), ("friendly", ct.c_wchar * 2048),
                ("launcher", ct.c_wchar * 2048)]


def check(status: int, operation: str) -> None:
    if status:
        raise OSError(f"NVAPI {operation} failed: status={status}")


def main() -> None:
    assert ct.sizeof(Setting) == 12320 and ct.sizeof(Application) == 12296
    if sys.argv[1:] == ["self-check"]:
        assert Setting.current.offset == 8220
        print("self-check passed")
        return
    if sys.argv[1:]:
        raise ValueError("Usage: fps_limit.py [self-check]")
    dll = ct.CDLL(r"C:\Windows\System32\nvapi64.dll")
    query = dll.nvapi_QueryInterface
    query.argtypes, query.restype = [U32], HANDLE

    def api(identifier: int, *types: type) -> Callable[..., int]:
        address = query(identifier)
        if not address:
            raise OSError(f"NVAPI interface unavailable: {identifier:#x}")
        return ct.CFUNCTYPE(ct.c_int, *types)(address)

    create = api(0x0694D52E, ct.POINTER(HANDLE))
    destroy = api(0xDAD9CFF8, HANDLE)
    load = api(0x375DBD6B, HANDLE)
    save = api(0xFCBC7E14, HANDLE)
    find = api(0xEEE566B2, HANDLE, ct.c_wchar_p, ct.POINTER(HANDLE), ct.POINTER(Application))
    get = api(0x73BF8338, HANDLE, HANDLE, U32, ct.POINTER(Setting))
    put = api(0x577DD202, HANDLE, HANDLE, ct.POINTER(Setting))
    delete = api(0xE4A26362, HANDLE, HANDLE, U32)
    check(api(0x0150E828)(), "Initialize")
    session, profile = HANDLE(), HANDLE()
    check(create(ct.byref(session)), "CreateSession")
    changed = False
    try:
        check(load(session), "LoadSettings")
        application = Application()
        application.version = ct.sizeof(application) | (1 << 16)
        check(find(session, GAME, ct.byref(profile), ct.byref(application)), "FindApplicationByName")
        original = Setting()
        original.version = ct.sizeof(original) | (1 << 16)
        original_status = get(session, profile, FPS_ID, ct.byref(original))
        if original_status != -160:  # NVAPI_SETTING_NOT_FOUND: implicit default, no stored override.
            check(original_status, "GetSetting")
        if original.kind != 0:
            raise ValueError("FPS setting is not DWORD")
        print(json.dumps({"status": "ready", "application": application.name,
                          "original_fps": original.current.number if original_status == 0 else None,
                          "location": original.location, "predefined": original.predefined}), flush=True)
        for line in sys.stdin:
            target = int(line)
            if target not in (30, 60, 120):
                raise ValueError("Only diagnostic FPS targets 30/60/120 are allowed")
            setting = Setting()
            setting.version = ct.sizeof(setting) | (1 << 16)
            setting.setting_id = FPS_ID
            setting.current.number = target
            check(put(session, profile, ct.byref(setting)), "SetSetting")
            changed = True
            check(save(session), "SaveSettings")
            check(get(session, profile, FPS_ID, ct.byref(setting)), "VerifySetting")
            if setting.current.number != target:
                raise RuntimeError("Driver FPS profile verification failed")
            print(json.dumps({"status": "capped", "fps": target}), flush=True)
    finally:
        try:
            if changed:
                if original_status == 0 and original.location == 0 and not original.predefined:
                    check(put(session, profile, ct.byref(original)), "RestoreSetting")
                else:
                    check(delete(session, profile, FPS_ID), "DeleteTemporaryOverride")
                check(save(session), "SaveRestoration")
                verify = Setting()
                verify.version = ct.sizeof(verify) | (1 << 16)
                restored_status = get(session, profile, FPS_ID, ct.byref(verify))
                if restored_status != original_status:
                    raise RuntimeError("Original FPS setting presence was not restored")
                if restored_status == 0 and (verify.current.number, verify.location, verify.predefined) != (
                        original.current.number, original.location, original.predefined):
                    raise RuntimeError("Original FPS profile setting was not restored")
                print(json.dumps({"status": "restored", "fps": verify.current.number if restored_status == 0 else None}), flush=True)
        finally:
            check(destroy(session), "DestroySession")


if __name__ == "__main__":
    main()
