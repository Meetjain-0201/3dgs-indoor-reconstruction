# 3DGS Indoor Reconstruction

End-to-end 3D Gaussian Splatting pipeline that turns a handheld webcam walkthrough of a room into a photorealistic scene you can fly through in the browser.

## Pipeline

```
+-----------+   +-----------+   +-----------+   +-----------+   +-----------+   +-----------+
| Raw Video |-->|   Frame   |-->|  COLMAP   |-->|   3DGS    |-->|  .ksplat  |-->| Three.js  |
|           |   | Extraction|   |    SfM    |   | Training  |   |  Export   |   |  Viewer   |
+-----------+   +-----------+   +-----------+   +-----------+   +-----------+   +-----------+
```

## Hardware and environment

Developed and tested on an NVIDIA RTX 5060 with 8 GB VRAM, 32 GB system RAM, running Ubuntu 22.04. Requires Python 3.10 or newer, conda, Node.js 18 or newer, and COLMAP 3.7 or newer.

## Setup

1. Install COLMAP from the system package manager:
   ```
   sudo apt install colmap
   ```

2. Clone the official 3DGS training repo and create its conda environment:
   ```
   bash scripts/setup_3dgs.sh
   ```

3. Clone the ksplat converter (it lives in the mkkellogg source tree, not in the published npm package):
   ```
   bash scripts/setup_viewer_converter.sh
   ```

4. Activate the 3DGS conda env and install the helper-script dependencies (frame extraction, monitoring, sparse visualization):
   ```
   conda activate gaussian_splatting
   pip install -r scripts/requirements.txt
   ```

5. Install the viewer's frontend dependencies:
   ```
   cd viewer && npm install
   ```

## Usage

Start from a short handheld walkthrough video. Aim for steady motion, good lighting, and plenty of overlap between adjacent frames. Everything below runs from the project root.

1. Extract sharp frames from the video, dropping blurry ones via a Laplacian variance threshold:
   ```
   python scripts/extract_frames.py --input path/to/bedroom.mp4 --output data/bedroom/images --fps 2
   ```

2. Scaffold the COLMAP-expected folder layout and record the scene in the manifest:
   ```
   python scripts/organize_scenes.py --scenes bedroom
   ```

3. Run Structure-from-Motion (use `--sequential` for video-derived frames since they are temporally ordered):
   ```
   python scripts/run_colmap.py --scene bedroom --sequential
   ```

4. Train 3D Gaussian Splatting on the posed images:
   ```
   bash scripts/train_scene.sh bedroom 30000
   ```

5. Export the trained point cloud to `.ksplat`, refresh the scenes index, and rebuild the viewer bundle:
   ```
   bash scripts/export_for_viewer.sh bedroom
   ```

6. Serve the viewer and open it in a browser:
   ```
   cd viewer && npm run dev
   ```

   Visit http://localhost:5173 and pick the scene from the landing page.

## Monitoring

Training runs for tens of minutes to several hours depending on iterations and scene size. `scripts/monitor_training.py` tails `output/<scene>/train.log` in real time by polling the file directly (no subprocess `tail`) and renders a live `rich` table of iteration, loss, PSNR, and elapsed time. It warns when the loss has not decreased in the last 3000 iterations and, on Ctrl+C, prints the best PSNR it observed along with the iteration where it was reached. Run it in a second terminal with `python scripts/monitor_training.py --scene bedroom --refresh_rate 5`.

## Evaluation

When the training script is invoked with `--eval` (the default in `train_scene.sh`), 3DGS saves held-out renders and matching ground-truth frames under `output/<scene>/test/ours_30000/`. `evaluation/evaluate.py` walks that pair directory, computes PSNR and SSIM via scikit-image and LPIPS (AlexNet backbone) via the `lpips` package, prints a per-image table with means, writes the full per-image results to `evaluation/<scene>_results.json`, and saves a four-pair visual comparison grid to `evaluation/<scene>_comparison.png` with rendered on top and ground truth on the bottom. Once multiple scenes have been evaluated, `evaluation/compare_scenes.py` reads every `*_results.json` in `evaluation/` and prints a single summary table sorted by mean PSNR descending.

## Results

| Scene | PSNR (dB) | SSIM | LPIPS |
|-------|-----------|------|-------|
|       |           |      |       |

## Known failure cases

The pipeline struggles where COLMAP and 3DGS traditionally struggle. Textureless surfaces such as painted walls and whiteboards give the feature matcher nothing to lock onto, so those regions come back sparse or drift between views. Specular reflections from monitors, windows, and glossy furniture confuse SfM triangulation and the appearance model at the same time, which shows up as floaters and view-dependent shimmer. Motion blur from a rushed sweep lowers the count of registered cameras, which starves the splat budget in exactly the parts of the room that needed the most coverage. Sparse coverage of corners, the "I forgot to walk around that end of the room" failure, produces stretched low-density Gaussians that look acceptable straight on and fall apart the moment the viewer orbits past them.

## References

Kerbl, B., Kopanas, G., Leimkuhler, T., and Drettakis, G. 2023. "3D Gaussian Splatting for Real-Time Radiance Field Rendering." ACM Transactions on Graphics 42(4).

Schonberger, J. L., and Frahm, J.-M. 2016. "Structure-from-Motion Revisited." In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR).
