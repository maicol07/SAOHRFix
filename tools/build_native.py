"""Build Windows x64 preview with Zig 0.15.2 and pinned MinHook 1.3.4."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MINHOOK = "c3fcafdc10146beb5919319d0683e44e3c30d537"

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zig", required=True, type=Path)
    parser.add_argument("--config", choices=("Debug", "Release"), required=True)
    args = parser.parse_args()
    zig = args.zig.resolve()
    if subprocess.check_output([str(zig), "version"], text=True).strip() != "0.15.2":
        raise ValueError("Zig 0.15.2 required")
    vendor = ROOT / ".cache/minhook"
    if not vendor.exists():
        subprocess.run(["git", "clone", "https://github.com/TsudaKageyu/minhook.git", str(vendor)], check=True)
        subprocess.run(["git", "-C", str(vendor), "checkout", "--detach", MINHOOK], check=True)
    if subprocess.check_output(["git", "-C", str(vendor), "rev-parse", "HEAD"], text=True).strip() != MINHOOK:
        raise ValueError("MinHook checkout differs from pinned commit")
    if subprocess.check_output(["git", "-C", str(vendor), "status", "--porcelain"], text=True).strip():
        raise ValueError("MinHook checkout must be unmodified")
    output = ROOT / ".cache/native" / args.config
    output.mkdir(parents=True, exist_ok=True)
    common = ["-target", "x86_64-windows-gnu", "-O0" if args.config == "Debug" else "-O2", "-g"]
    objects: list[str] = []
    for name in ("buffer.c", "hook.c", "trampoline.c", "hde/hde64.c"):
        obj = output / (Path(name).stem + ".o")
        subprocess.run([str(zig), "cc", *common, "-c", str(vendor / "src" / name), "-o", str(obj)], check=True)
        objects.append(str(obj))
    cpp = [str(zig), "c++", *common, "-std=c++17", "-Wall", "-Wextra", "-Werror"]
    if args.config == "Debug":
        cpp.append("-DSAOHRFIX_DEVELOPMENT=1")
    for source in ("tests.cpp", "activation_tests.cpp"):
        tests = output / (Path(source).stem + ".exe")
        subprocess.run([*cpp, "-UNDEBUG", str(ROOT / "native" / source), "-o", str(tests)], check=True)
        subprocess.run([str(tests)], check=True)
    hooks = output / "hook-tests.exe"
    subprocess.run([*cpp, "-UNDEBUG", str(ROOT / "native/hook_tests.cpp"), *objects,
                    "-I" + str(vendor / "include"), "-o", str(hooks)], check=True)
    subprocess.run([str(hooks)], check=True)
    subprocess.run([*cpp, "-shared", str(ROOT / "native/runtime.cpp"), *objects,
                    "-I" + str(vendor / "include"), "-lbcrypt", "-lxinput1_4", "-luser32",
                    "-o", str(output / "SAOHRFix.asi")], check=True)
    shutil.copy2(ROOT / "SAOHRFix.ini", output / "SAOHRFix.ini")
    shutil.copy2(vendor / "LICENSE.txt", output / "MinHook-LICENSE.txt")
    print(f"{args.config} build and native tests passed: {output}")

if __name__ == "__main__":
    main()
