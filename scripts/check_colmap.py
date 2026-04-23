"""
check_colmap.py

Verify that COLMAP is installed and callable, and print its version.

Exits 0 if COLMAP is on PATH and responds, 1 otherwise.

Usage:
    python check_colmap.py
"""

import shutil
import subprocess
import sys


def main():
    exe = shutil.which("colmap")
    if exe is None:
        print("colmap not found on PATH", file=sys.stderr)
        print("install instructions: https://colmap.github.io/install.html", file=sys.stderr)
        sys.exit(1)

    print(f"colmap found at: {exe}")

    for cmd in (["colmap", "--version"], ["colmap", "help"], ["colmap"]):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except FileNotFoundError:
            print("colmap disappeared between lookup and run", file=sys.stderr)
            sys.exit(1)
        except subprocess.TimeoutExpired:
            continue

        output = (result.stdout + result.stderr).strip()
        if output:
            first = output.splitlines()[0].strip()
            print(f"version: {first}")
            return

    print("colmap ran but produced no version output", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
