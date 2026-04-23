#!/usr/bin/env bash
# setup_viewer_converter.sh
# Clone the mkkellogg/GaussianSplats3D source tree into viewer/ksplat-converter/
# so we can run its util/create-ksplat.js converter. That utility ships in the
# source repo but not in the published npm tarball, so a plain `npm install`
# will not make it available.

set -u

REPO_URL="https://github.com/mkkellogg/GaussianSplats3D"
TARGET="viewer/ksplat-converter"

ok()   { printf "[ ok ] %s\n" "$*"; }
fail() { printf "[fail] %s\n" "$*" >&2; }

for cmd in git node npm; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        fail "$cmd not found on PATH"
        exit 1
    fi
done

if [[ -d "$TARGET/.git" ]]; then
    ok "step 1/2: $TARGET already cloned, skipping"
else
    if git clone "$REPO_URL" "$TARGET"; then
        ok "step 1/2: cloned $REPO_URL into $TARGET"
    else
        fail "step 1/2: git clone failed"
        exit 1
    fi
fi

if [[ -d "$TARGET/node_modules" ]]; then
    ok "step 2/2: $TARGET/node_modules already present, skipping install"
else
    if (cd "$TARGET" && npm install); then
        ok "step 2/2: installed converter dependencies"
    else
        fail "step 2/2: npm install failed inside $TARGET"
        exit 1
    fi
fi

echo
ok "ready. export_for_viewer.sh will use $TARGET/util/create-ksplat.js"
