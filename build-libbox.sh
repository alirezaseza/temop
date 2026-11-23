#!/usr/bin/env bash
set -euo pipefail
# Builds app/libs/libbox.aar from SagerNet/sing-box (make lib_install; make lib_android).
# VERIFY these steps against the sing-box docs for the tag you use; they change between versions.
# Needs: git, make, go, java (JDK 17), unzip, ANDROID_HOME (+ NDK).
SINGBOX_TAG="${SINGBOX_TAG:-v1.11.15}"
# Optional supply-chain pins: a tag can be moved, a commit cannot. Fill these once you have verified a build.
SINGBOX_COMMIT="${SINGBOX_COMMIT:-}"
LIBBOX_SHA256="${LIBBOX_SHA256:-}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
for cmd in git make go java unzip; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Missing required tool: $cmd"; exit 1; }
done
[[ -n "${ANDROID_HOME:-}" ]] || { echo "ANDROID_HOME is not set."; exit 1; }
export PATH="$(go env GOPATH)/bin:$PATH"
git clone --depth 1 --branch "$SINGBOX_TAG" https://github.com/SagerNet/sing-box.git "$WORK_DIR/sing-box"
cd "$WORK_DIR/sing-box"
RESOLVED_COMMIT="$(git rev-parse HEAD)"
echo "sing-box $SINGBOX_TAG resolved to commit $RESOLVED_COMMIT"
if [[ -n "$SINGBOX_COMMIT" && "$RESOLVED_COMMIT" != "$SINGBOX_COMMIT" ]]; then
  echo "Commit mismatch: expected $SINGBOX_COMMIT" >&2; exit 1
fi
make lib_install
make lib_android
AAR_PATH="$(find "$WORK_DIR/sing-box" -maxdepth 4 -name 'libbox.aar' | head -n 1 || true)"
[[ -n "$AAR_PATH" && -f "$AAR_PATH" ]] || { echo "libbox.aar not found after build."; exit 1; }
mkdir -p "$REPO_ROOT/app/libs"
cp "$AAR_PATH" "$REPO_ROOT/app/libs/libbox.aar"
ACTUAL_SHA="$(sha256sum "$REPO_ROOT/app/libs/libbox.aar" | cut -d' ' -f1)"
echo "libbox.aar sha256: $ACTUAL_SHA"
if [[ -n "$LIBBOX_SHA256" && "$ACTUAL_SHA" != "$LIBBOX_SHA256" ]]; then
  rm -f "$REPO_ROOT/app/libs/libbox.aar"; echo "libbox.aar checksum mismatch" >&2; exit 1
fi
unzip -l "$REPO_ROOT/app/libs/libbox.aar" | grep '\.so' || true
echo "Done: $REPO_ROOT/app/libs/libbox.aar"
