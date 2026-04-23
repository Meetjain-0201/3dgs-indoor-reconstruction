#!/usr/bin/env bash
# export_for_viewer.sh <scene_name>
# Convert a trained 3DGS point cloud into .ksplat, drop it in viewer/public/,
# refresh the scenes index, and rebuild the viewer bundle. Run from the
# project root.

set -u

SCENE="${1:-}"
if [[ -z "$SCENE" ]]; then
    echo "usage: $0 <scene_name>" >&2
    exit 1
fi

PLY="output/$SCENE/point_cloud/iteration_30000/point_cloud.ply"
PUBLIC_DIR="viewer/public"
CONVERTER_DIR="viewer/ksplat-converter"
CONVERTER="$CONVERTER_DIR/util/create-ksplat.js"
OUTPUT="$PUBLIC_DIR/$SCENE.ksplat"
INDEX_SCRIPT="scripts/update_scenes_index.py"

if [[ ! -f "$PLY" ]]; then
    echo "ERROR: $PLY not found. Train the scene to iteration 30000 first." >&2
    exit 1
fi

if [[ ! -d "$PUBLIC_DIR" ]]; then
    echo "ERROR: $PUBLIC_DIR does not exist. Initialize the viewer project first." >&2
    exit 1
fi

if [[ ! -f "$CONVERTER" ]]; then
    echo "ERROR: $CONVERTER not found. Run scripts/setup_viewer_converter.sh first." >&2
    exit 1
fi

# Absolute paths so the cd into the converter dir does not break the arguments.
PLY_ABS=$(cd "$(dirname "$PLY")" && pwd)/$(basename "$PLY")
OUTPUT_ABS=$(cd "$(dirname "$OUTPUT")" && pwd)/$(basename "$OUTPUT")

echo "converting $PLY -> $OUTPUT"
if ! (cd "$CONVERTER_DIR" && node util/create-ksplat.js "$PLY_ABS" "$OUTPUT_ABS"); then
    echo "ERROR: ksplat conversion failed" >&2
    exit 1
fi

if [[ ! -f "$OUTPUT" ]]; then
    echo "ERROR: converter did not produce $OUTPUT" >&2
    exit 1
fi

BYTES=$(wc -c < "$OUTPUT")
MB=$(awk -v b="$BYTES" 'BEGIN { printf "%.2f", b / 1048576 }')
echo "output size: ${MB} MB"

echo "updating scenes index..."
if ! python3 "$INDEX_SCRIPT"; then
    echo "ERROR: scenes index update failed" >&2
    exit 1
fi

echo "building viewer..."
if ! (cd viewer && npm run build); then
    echo "ERROR: viewer build failed" >&2
    exit 1
fi

echo
echo "Done. Run: cd viewer && npm run preview -- --open"
