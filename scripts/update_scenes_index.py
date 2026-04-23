"""
update_scenes_index.py

Scan viewer/public/ for *.ksplat files and write a JSON array of their
scene names (file stems, no extension) to viewer/public/scenes.json.

Called automatically by scripts/export_for_viewer.sh. Safe to run on its
own from the project root.

Usage:
    python scripts/update_scenes_index.py
"""

import json
import sys
from pathlib import Path

PUBLIC_DIR = Path("viewer/public")
OUT_FILE = PUBLIC_DIR / "scenes.json"


def main():
    if not PUBLIC_DIR.is_dir():
        print(f"ERROR: {PUBLIC_DIR} does not exist", file=sys.stderr)
        sys.exit(1)

    names = sorted(p.stem for p in PUBLIC_DIR.glob("*.ksplat"))
    OUT_FILE.write_text(json.dumps(names, indent=2) + "\n")
    print(f"wrote {OUT_FILE} with {len(names)} scene(s): {names}")


if __name__ == "__main__":
    main()
