"""
monitor_training.py

Live-tail a 3DGS training log for a given scene and show a rich table of
iteration / loss / PSNR / elapsed. Warns if training loss has plateaued,
and on Ctrl+C prints the best PSNR observed and the iteration it hit.

Reads output/<scene>/train.log. Polls the file directly (no subprocess
tail). If the log does not exist yet, waits for it to appear, printing
"Waiting for log file..." every 2 seconds.

Usage:
    python monitor_training.py --scene bedroom
    python monitor_training.py --scene workspace --refresh_rate 2
"""

import argparse
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text


ITER_RE = re.compile(r"(?:ITER|Iteration|iter)\s*[:=]?\s*(\d+)", re.IGNORECASE)
LOSS_RE = re.compile(r"loss\s*[:=]?\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", re.IGNORECASE)
PSNR_RE = re.compile(r"PSNR\s*[:=]?\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", re.IGNORECASE)
ELAPSED_RE = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)<")

STALE_LOSS_ITERS = 3000
LOG_FILE_POLL_SECONDS = 2.0
TABLE_TAIL = 20


def parse_args():
    p = argparse.ArgumentParser(description="live-tail 3DGS training log and show progress table")
    p.add_argument("--scene", required=True, help="scene name (reads output/<scene>/train.log)")
    p.add_argument("--refresh_rate", type=float, default=5.0,
                   help="seconds between log scans (default 5.0)")
    args = p.parse_args()
    if args.refresh_rate <= 0:
        p.error("--refresh_rate must be positive")
    return args


def parse_line(line):
    iter_m = ITER_RE.search(line)
    loss_m = LOSS_RE.search(line)
    psnr_m = PSNR_RE.search(line)
    elapsed_m = ELAPSED_RE.search(line)
    return {
        "iteration": int(iter_m.group(1)) if iter_m else None,
        "loss": float(loss_m.group(1)) if loss_m else None,
        "psnr": float(psnr_m.group(1)) if psnr_m else None,
        "elapsed": elapsed_m.group(1) if elapsed_m else None,
    }


def split_lines(buffer):
    """
    Split on any combination of \\r and \\n (tqdm uses \\r to overwrite progress
    bars, and once tee'd to a file that shows up in the stream).

    Returns (complete_lines, remainder). The remainder is whatever trailing
    text has no line terminator yet and should be kept for the next read.
    """
    if not buffer:
        return [], ""
    parts = re.split(r"[\r\n]+", buffer)
    if buffer[-1] in "\r\n":
        return [p for p in parts if p], ""
    return [p for p in parts[:-1] if p], parts[-1]


def build_renderable(entries, warning, best_psnr, best_psnr_iter):
    table = Table(show_header=True, header_style="bold")
    table.add_column("Iteration", justify="right")
    table.add_column("Loss", justify="right")
    table.add_column("PSNR (dB)", justify="right")
    table.add_column("Elapsed", justify="right")
    for it, v in list(entries.items())[-TABLE_TAIL:]:
        table.add_row(
            str(it),
            f"{v['loss']:.6f}" if v["loss"] is not None else "-",
            f"{v['psnr']:.4f}" if v["psnr"] is not None else "-",
            v["elapsed"] or "-",
        )

    pieces = [table]
    if best_psnr_iter is not None:
        pieces.append(Text(f"best PSNR so far: {best_psnr:.4f} dB at iter {best_psnr_iter}"))
    if warning:
        pieces.append(Text(warning, style="yellow"))
    return Group(*pieces)


def wait_for_log(log_path, console):
    while not log_path.exists():
        console.print(f"Waiting for log file... ({log_path})")
        time.sleep(LOG_FILE_POLL_SECONDS)


def main():
    args = parse_args()
    log_path = Path("output") / args.scene / "train.log"
    console = Console()

    wait_for_log(log_path, console)

    entries = OrderedDict()
    buffer = ""
    last_iter = None
    best_loss = float("inf")
    best_loss_iter = None
    best_psnr = float("-inf")
    best_psnr_iter = None

    try:
        with open(log_path, "r", errors="replace") as f, \
             Live(Text("initializing..."), console=console, auto_refresh=False) as live:
            while True:
                chunk = f.read()
                if chunk:
                    buffer += chunk
                    lines, buffer = split_lines(buffer)
                    for line in lines:
                        p = parse_line(line)
                        it = p["iteration"] if p["iteration"] is not None else last_iter
                        if it is None:
                            continue
                        entry = entries.setdefault(it, {"loss": None, "psnr": None, "elapsed": None})
                        if p["loss"] is not None:
                            entry["loss"] = p["loss"]
                            if p["loss"] < best_loss:
                                best_loss = p["loss"]
                                best_loss_iter = it
                        if p["psnr"] is not None:
                            entry["psnr"] = p["psnr"]
                            if p["psnr"] > best_psnr:
                                best_psnr = p["psnr"]
                                best_psnr_iter = it
                        if p["elapsed"] is not None:
                            entry["elapsed"] = p["elapsed"]
                        last_iter = it

                warning = None
                if (
                    last_iter is not None
                    and best_loss_iter is not None
                    and last_iter - best_loss_iter >= STALE_LOSS_ITERS
                ):
                    warning = (
                        f"WARN: loss has not decreased in {last_iter - best_loss_iter} "
                        f"iterations (best {best_loss:.6f} at iter {best_loss_iter})"
                    )

                live.update(
                    build_renderable(entries, warning, best_psnr, best_psnr_iter),
                    refresh=True,
                )
                time.sleep(args.refresh_rate)

    except KeyboardInterrupt:
        console.print()

    if best_psnr_iter is not None:
        console.print(f"best PSNR seen: {best_psnr:.4f} dB at iteration {best_psnr_iter}")
    else:
        console.print("no PSNR values observed in the log")


if __name__ == "__main__":
    main()
