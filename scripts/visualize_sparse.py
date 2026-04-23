"""
visualize_sparse.py

Load a scene's COLMAP sparse reconstruction and show it in Open3D for a
quick sanity check before training 3DGS.

Reads:
    <data_dir>/<scene>/sparse/0/points3D.txt
    <data_dir>/<scene>/sparse/0/images.txt

Renders:
    coloured sparse point cloud (RGB from points3D.txt)
    a small coordinate frame at each registered camera pose (from images.txt)

Saves a screenshot to docs/<scene>_sparse_preview.png and, by default, opens
an interactive window for inspection. Pass --headless to skip the window.

Usage:
    python visualize_sparse.py --scene bedroom
    python visualize_sparse.py --scene workspace --headless
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import open3d as o3d


def parse_args():
    p = argparse.ArgumentParser(description="visualize a COLMAP sparse reconstruction for a scene")
    p.add_argument("--scene", required=True, help="scene name under <data_dir>")
    p.add_argument("--data_dir", default="./data", help="root data directory (default: ./data)")
    p.add_argument("--docs_dir", default="./docs", help="where to save the preview PNG (default: ./docs)")
    p.add_argument("--headless", action="store_true", help="save screenshot and exit, no interactive window")
    p.add_argument("--frame_size", type=float, default=None,
                   help="coordinate-frame size for camera poses (default: 2%% of bbox diagonal)")
    return p.parse_args()


def load_points3d(path):
    xyz = []
    rgb = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            xyz.append([float(parts[1]), float(parts[2]), float(parts[3])])
            rgb.append([int(parts[4]), int(parts[5]), int(parts[6])])
    xyz = np.asarray(xyz, dtype=np.float64)
    rgb = np.asarray(rgb, dtype=np.float64) / 255.0
    return xyz, rgb


def load_images(path):
    """
    COLMAP images.txt stores two lines per image. We only need the first
    (pose) line; the second (2D observations) is skipped.
    """
    poses = []
    with open(path) as f:
        on_pose_line = True
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if on_pose_line:
                parts = line.split()
                qw, qx, qy, qz = (float(v) for v in parts[1:5])
                tx, ty, tz = (float(v) for v in parts[5:8])
                poses.append((qw, qx, qy, qz, tx, ty, tz))
                on_pose_line = False
            else:
                on_pose_line = True
    return poses


def quat_to_rotation_matrix(qw, qx, qy, qz):
    n = np.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if n == 0:
        return np.eye(3)
    qw, qx, qy, qz = qw / n, qx / n, qy / n, qz / n
    return np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw),     2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw),     1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw),     2 * (qy * qz + qx * qw),     1 - 2 * (qx * qx + qy * qy)],
    ])


def camera_to_world_transform(qw, qx, qy, qz, tx, ty, tz):
    """
    COLMAP stores world->camera pose. This returns the camera->world 4x4
    transform that places a coordinate frame at the camera position in
    world coordinates.
    """
    R_wc = quat_to_rotation_matrix(qw, qx, qy, qz)
    t_wc = np.array([tx, ty, tz])
    R_cw = R_wc.T
    C = -R_cw @ t_wc
    T = np.eye(4)
    T[:3, :3] = R_cw
    T[:3, 3] = C
    return T


def build_scene(xyz, rgb, poses, frame_size_override):
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(xyz)
    pcd.colors = o3d.utility.Vector3dVector(rgb)

    extent = pcd.get_axis_aligned_bounding_box().get_extent()
    diag = float(np.linalg.norm(extent))
    if frame_size_override is not None:
        frame_size = float(frame_size_override)
    else:
        frame_size = max(diag * 0.02, 1e-3)

    frames = []
    for pose in poses:
        T = camera_to_world_transform(*pose)
        frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=frame_size)
        frame.transform(T)
        frames.append(frame)

    return pcd, frames, frame_size


def render_and_capture(pcd, frames, screenshot_path, interactive):
    vis = o3d.visualization.Visualizer()
    vis.create_window(
        window_name=f"sparse preview ({screenshot_path.name})",
        width=1280,
        height=720,
        visible=interactive,
    )
    vis.add_geometry(pcd)
    for frame in frames:
        vis.add_geometry(frame)

    opt = vis.get_render_option()
    opt.background_color = np.asarray([0.05, 0.05, 0.05])
    opt.point_size = 2.0

    vis.poll_events()
    vis.update_renderer()
    vis.capture_screen_image(str(screenshot_path), do_render=True)

    if interactive:
        vis.run()
    vis.destroy_window()


def main():
    args = parse_args()

    scene_dir = Path(args.data_dir) / args.scene
    model_dir = scene_dir / "sparse" / "0"
    points_txt = model_dir / "points3D.txt"
    images_txt = model_dir / "images.txt"

    for required in (points_txt, images_txt):
        if not required.is_file():
            print(f"ERROR: {required} not found. Run run_colmap.py for this scene first.", file=sys.stderr)
            sys.exit(1)

    xyz, rgb = load_points3d(points_txt)
    if len(xyz) == 0:
        print(f"ERROR: {points_txt} has no points. Reconstruction likely failed.", file=sys.stderr)
        sys.exit(1)

    poses = load_images(images_txt)

    docs_dir = Path(args.docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = docs_dir / f"{args.scene}_sparse_preview.png"

    print(f"scene: {args.scene}")
    print(f"points: {len(xyz)}, cameras: {len(poses)}")
    print(f"screenshot: {screenshot_path}")

    pcd, frames, frame_size = build_scene(xyz, rgb, poses, args.frame_size)
    print(f"coordinate-frame size: {frame_size:.4f}")

    render_and_capture(pcd, frames, screenshot_path, interactive=not args.headless)

    print("done")


if __name__ == "__main__":
    main()
