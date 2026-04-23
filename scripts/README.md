# scripts/

Preprocessing and pipeline scripts.

Planned contents:

- `extract_frames.py` — sample frames from a webcam video at a target FPS.
- `run_colmap.sh` — feature extraction, matching, and sparse reconstruction via COLMAP.
- `prepare_dataset.py` — convert COLMAP output into the format expected by the 3DGS trainer.
- `train_3dgs.sh` — launch 3D Gaussian Splatting training.
- `export_splats.py` — export trained Gaussians to a format the Three.js viewer can load.
