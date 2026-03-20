#!/bin/bash
set -euo pipefail

export PKG_VERSION=$(pixi run python ../print_version.py)

echo "Building version: ${PKG_VERSION}"

OUTPUT_DIR="${1:-${HOME}/outdir}"
mkdir -p "${OUTPUT_DIR}"

# For staging builds, deploy the pixi.toml that includes ga-fdp/label/staging
if [ -n "${EXTRA_CHANNEL:-}" ]; then
    echo "Staging build: swapping in pixi-staging.toml"
    cp ../fdp_installer/pixi-staging.toml ../fdp_installer/pixi.toml
fi

rattler-build build \
  -c conda-forge \
  --output-dir "${OUTPUT_DIR}"
