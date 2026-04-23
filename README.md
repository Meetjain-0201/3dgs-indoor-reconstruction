# 3DGS Indoor Reconstruction

End-to-end 3D Gaussian Splatting pipeline for photorealistic indoor scene reconstruction. Takes raw webcam video, runs COLMAP SfM, trains 3DGS, and serves an interactive Three.js browser viewer.

## Pipeline

1. **Capture** — record a walkthrough video of an indoor scene with a standard webcam.
2. **Preprocess** — extract frames and run COLMAP Structure-from-Motion to recover camera poses and a sparse point cloud.
3. **Train** — fit a 3D Gaussian Splatting model to the posed images.
4. **Serve** — stream the trained splats to an interactive Three.js viewer in the browser.
5. **Evaluate** — compute PSNR / SSIM against held-out frames.

## Repository Layout

```
scripts/      preprocessing and pipeline scripts (frame extraction, COLMAP, training)
viewer/       Three.js web viewer
evaluation/   PSNR / SSIM evaluation scripts
docs/         notes, design decisions, failure case analysis
data/         input videos and intermediate artifacts (gitignored)
```

## Getting Started

See `scripts/README.md` for the preprocessing pipeline and `viewer/README.md` for running the web viewer.

## License

MIT — see `LICENSE`.

## Course

CS5330 final project.
