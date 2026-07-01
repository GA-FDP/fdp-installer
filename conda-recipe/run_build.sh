#!/bin/bash
set -euo pipefail

export PKG_VERSION=$(pixi run python ../print_version.py)

echo "Building version: ${PKG_VERSION}"

OUTPUT_DIR="${1:-${HOME}/outdir}"
mkdir -p "${OUTPUT_DIR}"

rattler-build build \
  -c conda-forge \
  --output-dir "${OUTPUT_DIR}"
