#!/usr/bin/env bash
# train_scene.sh <scene_name> [iterations]
# Train 3DGS on a COLMAP-prepared scene. Run from the project root.

set -u

SCENE="${1:-}"
ITERATIONS="${2:-30000}"
ENV_NAME="gaussian_splatting"
REPO_DIR="gaussian-splatting"

if [[ -z "$SCENE" ]]; then
    echo "usage: $0 <scene_name> [iterations]" >&2
    exit 1
fi

SCENE_ROOT="data/$SCENE"
OUTPUT_DIR="output/$SCENE"

# 3DGS only accepts PINHOLE / SIMPLE_PINHOLE cameras. If run_colmap.py ran the
# undistortion step, prefer the dense/ workspace (PINHOLE, already rectified).
# Otherwise fall back to the raw scene dir.
if [[ -d "$SCENE_ROOT/dense/images" ]] && [[ -d "$SCENE_ROOT/dense/sparse/0" ]]; then
    SCENE_DIR="$SCENE_ROOT/dense"
else
    SCENE_DIR="$SCENE_ROOT"
fi
IMAGES_DIR="$SCENE_DIR/images"

if [[ ! -d "$SCENE_ROOT" ]]; then
    echo "ERROR: scene directory $SCENE_ROOT does not exist." >&2
    exit 1
fi

if [[ ! -d "$IMAGES_DIR" ]] || [[ -z "$(ls -A "$IMAGES_DIR" 2>/dev/null)" ]]; then
    echo "ERROR: $IMAGES_DIR is missing or empty. Extract frames (and undistort) first." >&2
    exit 1
fi

if [[ ! -d "$REPO_DIR" ]]; then
    echo "ERROR: $REPO_DIR not found. Run scripts/setup_3dgs.sh first." >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

SCENE_DIR_ABS=$(cd "$SCENE_DIR" && pwd)
OUTPUT_DIR_ABS=$(cd "$OUTPUT_DIR" && pwd)
LOG="$OUTPUT_DIR_ABS/train.log"

CONDA_BASE=$(conda info --base 2>/dev/null || true)
if [[ -z "$CONDA_BASE" ]] || [[ ! -f "$CONDA_BASE/etc/profile.d/conda.sh" ]]; then
    echo "ERROR: conda not found or not initialized on PATH." >&2
    exit 1
fi
# shellcheck disable=SC1091
source "$CONDA_BASE/etc/profile.d/conda.sh"
if ! conda activate "$ENV_NAME"; then
    echo "ERROR: failed to activate conda env '$ENV_NAME'. Run scripts/setup_3dgs.sh first." >&2
    exit 1
fi

echo "scene:      $SCENE"
echo "iterations: $ITERATIONS"
echo "source:     $SCENE_DIR_ABS"
echo "output:     $OUTPUT_DIR_ABS"
echo "log:        $LOG"
echo

set -o pipefail
(
    cd "$REPO_DIR" && \
    python train.py \
        -s "$SCENE_DIR_ABS" \
        -m "$OUTPUT_DIR_ABS" \
        --iterations "$ITERATIONS" \
        --save_iterations 7000 15000 30000 \
        --checkpoint_iterations 7000 15000 30000 \
        --eval
) 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}
set +o pipefail

if [[ $status -ne 0 ]]; then
    echo "ERROR: training failed (exit $status). Check $LOG." >&2
    exit "$status"
fi

echo
echo "========== final PSNR =========="
psnr_line=$(grep -Ei "psnr" "$LOG" | tail -n 1)
if [[ -n "$psnr_line" ]]; then
    echo "$psnr_line"
else
    echo "(no PSNR line found in $LOG)"
fi
