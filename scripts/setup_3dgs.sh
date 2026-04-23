#!/usr/bin/env bash
# setup_3dgs.sh
# Clone the official 3DGS repo, init its submodules, and create the conda
# environment with Blackwell-compatible versions (PyTorch 2.7 + CUDA 12.8).
# Run from the project root.
#
# The upstream environment.yml pins Python 3.7 + PyTorch 1.x which does not
# support Blackwell (sm_120). We override it with scripts/environment_blackwell.yml
# and then build the 3DGS CUDA submodules with TORCH_CUDA_ARCH_LIST=12.0.

# Note: not using `set -u` because conda's cuda-nvcc activation script
# references NVCC_PREPEND_FLAGS before setting it, which trips nounset.

REPO_URL="https://github.com/graphdeco-inria/gaussian-splatting"
REPO_DIR="gaussian-splatting"
ENV_NAME="gaussian_splatting"
ENV_YML_SRC="scripts/environment_blackwell.yml"
ENV_YML_DST="$REPO_DIR/environment.yml"

ok()   { printf "[ ok ] %s\n" "$*"; }
fail() { printf "[fail] %s\n" "$*" >&2; }

step_clone() {
    if [[ -d "$REPO_DIR/.git" ]]; then
        ok "step 1/4: $REPO_DIR already present, skipping clone"
        return 0
    fi
    if git clone "$REPO_URL" "$REPO_DIR"; then
        ok "step 1/4: cloned $REPO_URL into $REPO_DIR"
    else
        fail "step 1/4: git clone failed"
        return 1
    fi
}

step_submodules() {
    if git -C "$REPO_DIR" submodule update --init --recursive; then
        ok "step 2/4: submodules initialized"
    else
        fail "step 2/4: submodule update failed"
        return 1
    fi
}

step_env() {
    if ! command -v conda >/dev/null 2>&1; then
        fail "step 3/4: conda not found on PATH. Install Miniconda or Anaconda first."
        return 1
    fi
    if conda env list | awk 'NF && $1 !~ /^#/ {print $1}' | grep -qx "$ENV_NAME"; then
        ok "step 3/4: conda env '$ENV_NAME' already exists, skipping create"
        return 0
    fi
    if [[ ! -f "$ENV_YML_SRC" ]]; then
        fail "step 3/4: $ENV_YML_SRC not found in this repo"
        return 1
    fi
    cp "$ENV_YML_SRC" "$ENV_YML_DST"
    ok "step 3/4: overrode $ENV_YML_DST with Blackwell-compatible env"
    if conda env create -f "$ENV_YML_DST"; then
        ok "step 3/4: conda env '$ENV_NAME' created"
    else
        fail "step 3/4: conda env create failed"
        return 1
    fi
}

step_submodule_extensions() {
    local conda_base
    conda_base=$(conda info --base 2>/dev/null)
    if [[ -z "$conda_base" ]] || [[ ! -f "$conda_base/etc/profile.d/conda.sh" ]]; then
        fail "step 4/4: could not source conda.sh"
        return 1
    fi
    # shellcheck disable=SC1091
    source "$conda_base/etc/profile.d/conda.sh"
    if ! conda activate "$ENV_NAME"; then
        fail "step 4/4: failed to activate $ENV_NAME"
        return 1
    fi

    # Quick check: are the extensions already installed?
    if python - <<'PY' 2>/dev/null
import importlib, sys
for name in ("diff_gaussian_rasterization", "simple_knn", "fused_ssim"):
    importlib.import_module(name)
PY
    then
        ok "step 4/4: CUDA extensions already importable, skipping rebuild"
        return 0
    fi

    export TORCH_CUDA_ARCH_LIST="12.0"
    # --no-build-isolation so setup.py can import torch from the active env
    # (modern pip otherwise runs the build in a clean sandbox without torch).
    if pip install --no-build-isolation \
            "$REPO_DIR/submodules/diff-gaussian-rasterization" \
            "$REPO_DIR/submodules/simple-knn" \
            "$REPO_DIR/submodules/fused-ssim"; then
        ok "step 4/4: built 3DGS CUDA extensions for sm_120"
    else
        fail "step 4/4: CUDA extension build failed"
        return 1
    fi
}

step_clone                 || exit 1
step_submodules            || exit 1
step_env                   || exit 1
step_submodule_extensions  || exit 1

echo
ok "3DGS setup complete. Activate the env with: conda activate $ENV_NAME"
