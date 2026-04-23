#!/usr/bin/env bash
# setup_3dgs.sh
# Clone the official 3DGS repo, init its submodules, and create the conda
# environment it ships with. Run from the project root.

set -u

REPO_URL="https://github.com/graphdeco-inria/gaussian-splatting"
REPO_DIR="gaussian-splatting"
ENV_NAME="gaussian_splatting"
ENV_YML="$REPO_DIR/environment.yml"

ok()   { printf "[ ok ] %s\n" "$*"; }
fail() { printf "[fail] %s\n" "$*" >&2; }

step_clone() {
    if [[ -d "$REPO_DIR/.git" ]]; then
        ok "step 1/3: $REPO_DIR already present, skipping clone"
        return 0
    fi
    if git clone "$REPO_URL" "$REPO_DIR"; then
        ok "step 1/3: cloned $REPO_URL into $REPO_DIR"
    else
        fail "step 1/3: git clone failed"
        return 1
    fi
}

step_submodules() {
    if git -C "$REPO_DIR" submodule update --init --recursive; then
        ok "step 2/3: submodules initialized"
    else
        fail "step 2/3: submodule update failed"
        return 1
    fi
}

step_env() {
    if ! command -v conda >/dev/null 2>&1; then
        fail "step 3/3: conda not found on PATH. Install Miniconda or Anaconda first."
        return 1
    fi
    if conda env list | awk 'NF && $1 !~ /^#/ {print $1}' | grep -qx "$ENV_NAME"; then
        ok "step 3/3: conda env '$ENV_NAME' already exists, skipping create"
        return 0
    fi
    if [[ ! -f "$ENV_YML" ]]; then
        fail "step 3/3: $ENV_YML not found"
        return 1
    fi
    if conda env create -f "$ENV_YML"; then
        ok "step 3/3: conda env '$ENV_NAME' created from $ENV_YML"
    else
        fail "step 3/3: conda env create failed"
        return 1
    fi
}

step_clone      || exit 1
step_submodules || exit 1
step_env        || exit 1

echo
ok "3DGS setup complete. Activate the env with: conda activate $ENV_NAME"
