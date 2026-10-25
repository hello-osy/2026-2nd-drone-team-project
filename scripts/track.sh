#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /opt/ros/jazzy/setup.bash
source .venv/bin/activate
export ROS_DOMAIN_ID=0
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export YOLO_CONFIG_DIR="$PWD/.cache/ultralytics"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
exec python -m pd_drone.app "$@"
