#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
export YOLO_CONFIG_DIR="$PWD/.cache/ultralytics"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
mkdir -p "$YOLO_CONFIG_DIR"
exec .venv/bin/python src/pd_drone/train_detector.py "$@"
