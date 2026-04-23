"""
extract_frames.py

Pull sharp frames out of a video for the 3DGS preprocessing pipeline.

Samples frames at a target FPS with ffmpeg, rejects blurry ones using the
Laplacian variance test (threshold 100), resizes anything larger than
1280x720, and writes survivors as frame_XXXXX.jpg.

Usage:
    python extract_frames.py --input scene.mp4 --output frames/ --fps 2
    python extract_frames.py --input scene.mp4 --output frames/ --dry_run
"""

import argparse
import os
import sys

import cv2
import ffmpeg
import numpy as np


BLUR_THRESHOLD = 100.0
MAX_W = 1280
MAX_H = 720


def probe_video(path):
    info = ffmpeg.probe(path)
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    return int(stream["width"]), int(stream["height"])


def iter_frames(path, fps, width, height):
    proc = (
        ffmpeg
        .input(path)
        .filter("fps", fps=fps)
        .output("pipe:", format="rawvideo", pix_fmt="bgr24")
        .run_async(pipe_stdout=True)
    )
    frame_bytes = width * height * 3
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            yield np.frombuffer(buf, np.uint8).reshape((height, width, 3))
    finally:
        proc.stdout.close()
        proc.wait()


def laplacian_variance(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def maybe_resize(img):
    h, w = img.shape[:2]
    if w <= MAX_W and h <= MAX_H:
        return img
    scale = min(MAX_W / w, MAX_H / h)
    new_w, new_h = int(round(w * scale)), int(round(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def parse_args():
    p = argparse.ArgumentParser(description="extract sharp frames from a video")
    p.add_argument("--input", required=True, help="path to input video")
    p.add_argument("--output", required=True, help="output directory for frames")
    p.add_argument("--fps", type=float, default=2.0, help="sampling rate in frames per second (default 2)")
    p.add_argument("--max_frames", type=int, default=500, help="stop after this many saved frames (default 500)")
    p.add_argument("--dry_run", action="store_true", help="run blur detection without writing anything")
    return p.parse_args()


def main():
    args = parse_args()

    if not os.path.isfile(args.input):
        print(f"input not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not args.dry_run:
        os.makedirs(args.output, exist_ok=True)

    width, height = probe_video(args.input)

    total = 0
    skipped = 0
    saved = 0

    for frame in iter_frames(args.input, args.fps, width, height):
        total += 1
        if laplacian_variance(frame) < BLUR_THRESHOLD:
            skipped += 1
            continue

        out = maybe_resize(frame)
        if not args.dry_run:
            path = os.path.join(args.output, f"frame_{saved:05d}.jpg")
            cv2.imwrite(path, out)
        saved += 1

        if saved >= args.max_frames:
            break

    suffix = " (dry run, nothing written)" if args.dry_run else ""
    print(f"total sampled: {total}")
    print(f"skipped (blurry, var<{BLUR_THRESHOLD:g}): {skipped}")
    print(f"frames saved: {saved}{suffix}")


if __name__ == "__main__":
    main()
