"""
evaluate.py

Evaluate 3DGS test-set renders against ground truth. Computes PSNR, SSIM,
and LPIPS for every matching (filename) pair between the rendered and GT
directories, prints a per-image table plus means, dumps full results to
evaluation/<scene>_results.json, and saves a 4-pair visual comparison grid
to evaluation/<scene>_comparison.png (top row rendered, bottom row GT).

Expects the 3DGS render layout:
    output/<scene>/test/ours_<iteration>/renders/*.png
    output/<scene>/test/ours_<iteration>/gt/*.png

Usage:
    python evaluation/evaluate.py --scene bedroom
    python evaluation/evaluate.py --scene workspace --iteration 15000
"""

import argparse
import json
import random
import sys
from pathlib import Path

import imageio.v2 as imageio
import lpips
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from skimage.metrics import peak_signal_noise_ratio, structural_similarity
from tabulate import tabulate


IMG_EXTS = {".png", ".jpg", ".jpeg"}


def parse_args():
    p = argparse.ArgumentParser(description="PSNR / SSIM / LPIPS for a 3DGS test set")
    p.add_argument("--scene", required=True, help="scene name under output/")
    p.add_argument("--iteration", type=int, default=30000, help="iteration tag (default 30000)")
    return p.parse_args()


def load_image(path):
    arr = imageio.imread(str(path))
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.shape[-1] == 4:
        arr = arr[..., :3]
    return arr.astype(np.float32) / 255.0


def ssim_rgb(a, b):
    """
    Use channel_axis=-1 on modern skimage. Fall back to the legacy
    `multichannel=True` for pre-0.19 installs where channel_axis didn't exist.
    """
    try:
        return structural_similarity(a, b, channel_axis=-1, data_range=1.0)
    except TypeError:
        return structural_similarity(a, b, multichannel=True, data_range=1.0)


def lpips_value(model, rendered, gt, device):
    # HxWx3 float [0,1] -> 1x3xHxW float [-1,1]
    def to_tensor(a):
        t = torch.from_numpy(a).permute(2, 0, 1).unsqueeze(0).to(device)
        return t * 2 - 1
    with torch.no_grad():
        return model(to_tensor(rendered), to_tensor(gt)).item()


def build_comparison_grid(pairs, scene, out_path, cell_w=400):
    if not pairs:
        return None

    def to_pil(arr):
        return Image.fromarray((arr * 255).clip(0, 255).astype(np.uint8))

    first_rendered = pairs[0][1]
    h0, w0 = first_rendered.shape[:2]
    cell_h = int(round(h0 * (cell_w / w0)))
    label_h = 24
    pad = 6
    header_h = 22

    n = len(pairs)
    grid_w = n * cell_w + (n + 1) * pad
    grid_h = header_h + 2 * cell_h + label_h + 3 * pad

    img = Image.new("RGB", (grid_w, grid_h), color=(10, 10, 15))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
    except OSError:
        font = ImageFont.load_default()

    draw.text(
        (pad, 4),
        f"scene: {scene}    top: rendered    bottom: ground truth",
        fill=(180, 180, 190),
        font=font,
    )

    for i, (name, rendered, gt) in enumerate(pairs):
        x = pad + i * (cell_w + pad)
        y_top = header_h + pad
        y_label = y_top + cell_h
        y_bot = y_label + label_h

        pil_r = to_pil(rendered).resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        pil_g = to_pil(gt).resize((cell_w, cell_h), Image.Resampling.LANCZOS)

        img.paste(pil_r, (x, y_top))
        draw.text((x + 4, y_label + 4), name, fill=(232, 232, 238), font=font)
        img.paste(pil_g, (x, y_bot))

    img.save(out_path)
    return out_path


def main():
    args = parse_args()

    base = Path("output") / args.scene / "test" / f"ours_{args.iteration}"
    render_dir = base / "renders"
    gt_dir = base / "gt"

    for d in (render_dir, gt_dir):
        if not d.is_dir():
            print(
                f"ERROR: {d} does not exist. Train with --eval and render test views first.",
                file=sys.stderr,
            )
            sys.exit(1)

    render_files = {p.name: p for p in render_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in IMG_EXTS}
    gt_files = {p.name: p for p in gt_dir.iterdir()
                if p.is_file() and p.suffix.lower() in IMG_EXTS}

    if not render_files:
        print(f"ERROR: {render_dir} contains no image files.", file=sys.stderr)
        sys.exit(1)
    if not gt_files:
        print(f"ERROR: {gt_dir} contains no image files.", file=sys.stderr)
        sys.exit(1)

    common = sorted(set(render_files) & set(gt_files))
    if not common:
        print(
            f"ERROR: no matching filenames between {render_dir} and {gt_dir}.",
            file=sys.stderr,
        )
        sys.exit(1)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    lpips_model = lpips.LPIPS(net="alex").to(device)
    lpips_model.eval()

    rows = []
    per_image = []
    grid_candidates = []

    for name in common:
        rendered = load_image(render_files[name])
        gt = load_image(gt_files[name])

        if rendered.shape != gt.shape:
            print(
                f"WARN: shape mismatch on {name}: rendered {rendered.shape} vs gt {gt.shape}. Skipping.",
                file=sys.stderr,
            )
            continue

        psnr = float(peak_signal_noise_ratio(gt, rendered, data_range=1.0))
        ssim = float(ssim_rgb(gt, rendered))
        lp = float(lpips_value(lpips_model, rendered, gt, device))

        rows.append([name, f"{psnr:.4f}", f"{ssim:.4f}", f"{lp:.4f}"])
        per_image.append({"filename": name, "psnr": psnr, "ssim": ssim, "lpips": lp})
        grid_candidates.append((name, rendered, gt))

    if not per_image:
        print("ERROR: no valid image pairs after shape check.", file=sys.stderr)
        sys.exit(1)

    mean_psnr = float(np.mean([r["psnr"] for r in per_image]))
    mean_ssim = float(np.mean([r["ssim"] for r in per_image]))
    mean_lpips = float(np.mean([r["lpips"] for r in per_image]))

    rows.append(["mean", f"{mean_psnr:.4f}", f"{mean_ssim:.4f}", f"{mean_lpips:.4f}"])
    print(tabulate(rows, headers=["Filename", "PSNR", "SSIM", "LPIPS"], tablefmt="github"))

    eval_dir = Path("evaluation")
    eval_dir.mkdir(parents=True, exist_ok=True)

    results_path = eval_dir / f"{args.scene}_results.json"
    results_path.write_text(json.dumps({
        "scene": args.scene,
        "iteration": args.iteration,
        "per_image": per_image,
        "summary": {
            "mean_psnr": mean_psnr,
            "mean_ssim": mean_ssim,
            "mean_lpips": mean_lpips,
            "n_pairs": len(per_image),
        },
    }, indent=2) + "\n")
    print(f"\nresults: {results_path}")

    random.seed(0)
    k = min(4, len(grid_candidates))
    picks = random.sample(grid_candidates, k)
    grid_path = eval_dir / f"{args.scene}_comparison.png"
    build_comparison_grid(picks, args.scene, grid_path)
    print(f"comparison grid: {grid_path}")


if __name__ == "__main__":
    main()
