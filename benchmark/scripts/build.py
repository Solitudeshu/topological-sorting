"""Build without requiring CMake; g++/clang++ must be on PATH."""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build(debug=False):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        raise SystemExit("Install a C++17 compiler or use the supplied CMakeLists.txt.")
    dest = ROOT / "benchmark/build"
    dest.mkdir(parents=True, exist_ok=True)
    for source, name in [
        ("src/runner.cpp", "topo_bench"),
        ("tests/test_topo.cpp", "topo_tests"),
    ]:
        command = [
            compiler,
            "-std=c++17",
            "-O0" if debug else "-O3",
            "-g" if debug else "-DNDEBUG",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-I",
            str(ROOT / "benchmark/include"),
            str(ROOT / "benchmark" / source),
            "-o",
            str(dest / (name + (".exe" if os.name == "nt" else ""))),
        ]
        subprocess.run(command, check=True)
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    print(build(parser.parse_args().debug))
