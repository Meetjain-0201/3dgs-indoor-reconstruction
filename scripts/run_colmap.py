"""
run_colmap.py

Drive the full COLMAP Structure-from-Motion pipeline for a single scene:
feature extraction, matching (exhaustive or sequential), sparse reconstruction
(mapper), and conversion of the resulting model to TXT form.

Every subprocess has its stdout and stderr streamed to the terminal and
appended to data/<scene>/colmap_<scene>.log, with the exact command logged
before it runs. Any non-zero exit aborts the pipeline with a clear message.

After the mapper finishes, the script parses sparse/0/cameras.txt and
sparse/0/points3D.txt and prints a short reconstruction summary: camera
count, focal length, principal point, 3D point count, mean reprojection
error.

Usage:
    python run_colmap.py --scene bedroom
    python run_colmap.py --scene workspace --sequential
    python run_colmap.py --scene kitchen --no-use_gpu
"""

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="run the COLMAP SfM pipeline for a scene")
    p.add_argument("--scene", required=True, help="scene name under <data_dir>")
    p.add_argument("--data_dir", default="./data", help="root data directory (default: ./data)")
    p.add_argument(
        "--use_gpu",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable GPU for SIFT extraction and matching (default: on; pass --no-use_gpu to disable)",
    )
    p.add_argument(
        "--sequential",
        action="store_true",
        help="Use for video input where frames are temporally ordered.",
    )
    return p.parse_args()


def feature_extractor_cmd(db_path, image_path, use_gpu):
    return [
        "colmap", "feature_extractor",
        "--database_path", str(db_path),
        "--image_path", str(image_path),
        "--ImageReader.single_camera", "1",
        "--ImageReader.camera_model", "OPENCV",
        "--SiftExtraction.use_gpu", "1" if use_gpu else "0",
    ]


def matcher_cmd(db_path, sequential, use_gpu):
    sub = "sequential_matcher" if sequential else "exhaustive_matcher"
    return [
        "colmap", sub,
        "--database_path", str(db_path),
        "--SiftMatching.use_gpu", "1" if use_gpu else "0",
    ]


def mapper_cmd(db_path, image_path, sparse_path):
    return [
        "colmap", "mapper",
        "--database_path", str(db_path),
        "--image_path", str(image_path),
        "--output_path", str(sparse_path),
    ]


def model_converter_cmd(model_path):
    return [
        "colmap", "model_converter",
        "--input_path", str(model_path),
        "--output_path", str(model_path),
        "--output_type", "TXT",
    ]


def image_undistorter_cmd(image_path, sparse_model_path, dense_path):
    return [
        "colmap", "image_undistorter",
        "--image_path", str(image_path),
        "--input_path", str(sparse_model_path),
        "--output_path", str(dense_path),
        "--output_type", "COLMAP",
        "--max_image_size", "2000",
    ]


def run_step(cmd, log_path, step_name):
    pretty = shlex.join(cmd)
    banner = f"\n========== {step_name} ==========\ncommand: {pretty}\n"
    print(banner, end="", flush=True)
    with open(log_path, "a") as log:
        log.write(banner)
        log.flush()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        proc.wait()
        log.write(f"---- exit: {proc.returncode} ----\n")

    if proc.returncode != 0:
        print(
            f"\nERROR: {step_name} failed with exit code {proc.returncode}. "
            f"See {log_path} for the full log.",
            file=sys.stderr,
        )
        sys.exit(1)


def parse_cameras_txt(path):
    cams = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            cams.append({
                "id": parts[0],
                "model": parts[1],
                "width": int(parts[2]),
                "height": int(parts[3]),
                "params": [float(x) for x in parts[4:]],
            })
    return cams


def camera_focal_and_pp(cam):
    model = cam["model"]
    params = cam["params"]
    if model in ("PINHOLE", "OPENCV", "FULL_OPENCV", "OPENCV_FISHEYE"):
        fx, fy, cx, cy = params[0], params[1], params[2], params[3]
    elif model in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"):
        fx = fy = params[0]
        cx, cy = params[1], params[2]
    else:
        fx = fy = params[0]
        cx = params[1] if len(params) > 1 else cam["width"] / 2.0
        cy = params[2] if len(params) > 2 else cam["height"] / 2.0
    return fx, fy, cx, cy


def summarize_cameras(cams):
    print(f"cameras: {len(cams)}")
    for cam in cams:
        fx, fy, cx, cy = camera_focal_and_pp(cam)
        print(
            f"  id={cam['id']} model={cam['model']} "
            f"size={cam['width']}x{cam['height']} "
            f"focal=({fx:.2f}, {fy:.2f}) "
            f"principal=({cx:.2f}, {cy:.2f})"
        )


def parse_points3d_stats(path):
    count = 0
    err_sum = 0.0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            err_sum += float(parts[7])
            count += 1
    mean_err = err_sum / count if count else float("nan")
    return count, mean_err


def main():
    args = parse_args()

    if shutil.which("colmap") is None:
        print("ERROR: colmap not found on PATH. Install it and retry.", file=sys.stderr)
        sys.exit(1)

    scene_dir = Path(args.data_dir) / args.scene
    images_dir = scene_dir / "images"
    sparse_dir = scene_dir / "sparse"
    db_path = scene_dir / "database.db"
    log_path = scene_dir / f"colmap_{args.scene}.log"

    if not images_dir.is_dir():
        print(
            f"ERROR: {images_dir} does not exist. "
            f"Run organize_scenes.py and extract frames first.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not any(images_dir.iterdir()):
        print(f"ERROR: {images_dir} is empty. Extract frames before running COLMAP.", file=sys.stderr)
        sys.exit(1)

    sparse_dir.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as f:
        f.write(f"colmap pipeline log for scene '{args.scene}'\n")

    matcher_name = "sequential_matcher" if args.sequential else "exhaustive_matcher"
    print(f"scene: {args.scene}")
    print(f"data_dir: {args.data_dir}")
    print(f"matcher: {matcher_name}")
    print(f"gpu: {'on' if args.use_gpu else 'off'}")
    print(f"log: {log_path}")

    run_step(feature_extractor_cmd(db_path, images_dir, args.use_gpu), log_path, "feature_extractor")
    run_step(matcher_cmd(db_path, args.sequential, args.use_gpu), log_path, matcher_name)
    run_step(mapper_cmd(db_path, images_dir, sparse_dir), log_path, "mapper")

    model_dir = sparse_dir / "0"
    if not model_dir.is_dir():
        print(
            f"ERROR: mapper did not produce {model_dir}. "
            f"This usually means too few matches were found. See {log_path}.",
            file=sys.stderr,
        )
        sys.exit(1)

    run_step(model_converter_cmd(model_dir), log_path, "model_converter")

    # 3DGS only accepts PINHOLE / SIMPLE_PINHOLE. We use OPENCV in feature
    # extraction (better distortion modeling during BA), so undistort the
    # images and resulting model here. Output goes to <scene>/dense/ and
    # has sparse wrapped in 0/ the way 3DGS expects.
    dense_dir = scene_dir / "dense"
    if dense_dir.exists():
        import shutil
        shutil.rmtree(dense_dir)
    run_step(image_undistorter_cmd(images_dir, model_dir, dense_dir), log_path, "image_undistorter")

    dense_sparse = dense_dir / "sparse"
    if dense_sparse.is_dir() and not (dense_sparse / "0").exists():
        tmp = dense_dir / "sparse_flat"
        dense_sparse.rename(tmp)
        dense_sparse.mkdir()
        tmp.rename(dense_sparse / "0")

    cameras_txt = model_dir / "cameras.txt"
    points_txt = model_dir / "points3D.txt"
    if not cameras_txt.is_file() or not points_txt.is_file():
        print(
            f"ERROR: expected TXT model files not found in {model_dir}. See {log_path}.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\n========== reconstruction summary ==========")
    cams = parse_cameras_txt(cameras_txt)
    summarize_cameras(cams)
    n_points, mean_err = parse_points3d_stats(points_txt)
    print(f"3D points: {n_points}")
    print(f"mean reprojection error: {mean_err:.4f} px")


if __name__ == "__main__":
    main()
