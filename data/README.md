# data/

Input videos and intermediate artifacts live here. Everything in this folder is gitignored except this README.

Expected layout per scene:

```
data/<scene_name>/
    raw.mp4              # the source webcam capture
    frames/              # extracted frames
    colmap/              # COLMAP workspace (sparse/, database.db, ...)
    splats/              # trained 3DGS checkpoints and exports
```

Nothing under `data/` should be committed — it's large, often private, and reproducible from the source video via `scripts/`.
