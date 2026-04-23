"""
compare_scenes.py

Summary table across all scenes that have been evaluated. Scans evaluation/
for *_results.json, reads each summary block, prints one table sorted by
mean PSNR descending.

Usage:
    python evaluation/compare_scenes.py
"""

import json
import sys
from pathlib import Path

from tabulate import tabulate


EVAL_DIR = Path("evaluation")


def main():
    if not EVAL_DIR.is_dir():
        print(f"ERROR: {EVAL_DIR} not found", file=sys.stderr)
        sys.exit(1)

    rows = []
    for path in sorted(EVAL_DIR.glob("*_results.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            print(f"WARN: skipping {path}: {e}", file=sys.stderr)
            continue
        summary = data.get("summary", {})
        rows.append({
            "scene": data.get("scene", path.stem.replace("_results", "")),
            "iteration": data.get("iteration", "-"),
            "mean_psnr": summary.get("mean_psnr"),
            "mean_ssim": summary.get("mean_ssim"),
            "mean_lpips": summary.get("mean_lpips"),
        })

    if not rows:
        print("no *_results.json files found in evaluation/. run evaluate.py first.")
        sys.exit(0)

    rows.sort(
        key=lambda r: r["mean_psnr"] if r["mean_psnr"] is not None else float("-inf"),
        reverse=True,
    )

    table = [
        [
            r["scene"],
            r["iteration"],
            f"{r['mean_psnr']:.4f}" if r["mean_psnr"] is not None else "-",
            f"{r['mean_ssim']:.4f}" if r["mean_ssim"] is not None else "-",
            f"{r['mean_lpips']:.4f}" if r["mean_lpips"] is not None else "-",
        ]
        for r in rows
    ]
    print(tabulate(
        table,
        headers=["Scene", "Iteration", "Mean PSNR", "Mean SSIM", "Mean LPIPS"],
        tablefmt="github",
    ))


if __name__ == "__main__":
    main()
