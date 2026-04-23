"""
organize_scenes.py

Scaffold the COLMAP-expected folder layout for one or more scenes and keep
a small JSON manifest of what's been set up.

For each scene in --scenes, creates:
    <data_dir>/<scene>/images/
    <data_dir>/<scene>/sparse/
    <data_dir>/<scene>/dense/

and upserts an entry in <data_dir>/scenes_config.json with the scene name,
current image count (counted from images/), and creation timestamp.

Usage:
    python organize_scenes.py --scenes bedroom workspace
    python organize_scenes.py --scenes kitchen --data_dir data
"""

import argparse
import datetime
import json
import os


SUBDIRS = ["images", "sparse", "dense"]
IMG_EXTS = {".jpg", ".jpeg", ".png"}


def count_images(images_dir):
    if not os.path.isdir(images_dir):
        return 0
    return sum(
        1 for name in os.listdir(images_dir)
        if os.path.splitext(name)[1].lower() in IMG_EXTS
    )


def load_config(path):
    if not os.path.isfile(path):
        return {"scenes": []}
    with open(path) as f:
        return json.load(f)


def save_config(path, cfg):
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def upsert_scene(cfg, name, image_count, created_at):
    for entry in cfg["scenes"]:
        if entry["name"] == name:
            entry["image_count"] = image_count
            return False
    cfg["scenes"].append({
        "name": name,
        "image_count": image_count,
        "created_at": created_at,
    })
    return True


def print_tree(data_dir, scenes):
    print(f"{data_dir}/")
    entries = [(name + "/", True) for name in scenes]
    entries.append(("scenes_config.json", False))
    for i, (entry, is_scene) in enumerate(entries):
        last = i == len(entries) - 1
        branch = "└── " if last else "├── "
        child_prefix = "    " if last else "│   "
        print(f"{branch}{entry}")
        if is_scene:
            for j, sub in enumerate(SUBDIRS):
                sub_last = j == len(SUBDIRS) - 1
                print(f"{child_prefix}{'└── ' if sub_last else '├── '}{sub}/")


def parse_args():
    p = argparse.ArgumentParser(description="scaffold COLMAP folder layout for scenes")
    p.add_argument("--scenes", nargs="+", required=True, help="scene names, e.g. --scenes bedroom workspace")
    p.add_argument("--data_dir", default="data", help="root data directory (default: data)")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.data_dir, exist_ok=True)

    config_path = os.path.join(args.data_dir, "scenes_config.json")
    cfg = load_config(config_path)

    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    created, updated = 0, 0
    for name in args.scenes:
        scene_dir = os.path.join(args.data_dir, name)
        for sub in SUBDIRS:
            os.makedirs(os.path.join(scene_dir, sub), exist_ok=True)
        n_images = count_images(os.path.join(scene_dir, "images"))
        if upsert_scene(cfg, name, n_images, created_at):
            created += 1
        else:
            updated += 1

    save_config(config_path, cfg)

    print_tree(args.data_dir, args.scenes)
    print()
    print(f"created {created} new, updated {updated} existing")
    print(f"config: {config_path}")


if __name__ == "__main__":
    main()
