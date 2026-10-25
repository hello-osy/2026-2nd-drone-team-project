#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export YOLO_CONFIG_DIR="$PWD/.cache/ultralytics"
mkdir -p logs "$YOLO_CONFIG_DIR"
exec .venv/bin/python -m pd_drone.capture "$@"
