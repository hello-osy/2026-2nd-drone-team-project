#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
export GZ_SIM_RESOURCE_PATH="$ROOT/src/simulation/models:$ROOT/external/PX4-Autopilot/Tools/simulation/gz/models${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$ROOT/external/build/pd_ball${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1
unset WAYLAND_DISPLAY
test -f external/build/pd_ball/libpd_ball.so || { echo 'Run bash setup.sh first'; exit 1; }
mkdir -p logs
if timeout 3 gz topic -l 2>/dev/null | grep -q '^/world/.*/clock$'; then
  echo 'Another Gazebo world is running. Stop it before starting soccer.'
  exit 1
fi
# Separate server: owned world and Ogre1 sensor plugin, with upstream PX4 untouched.
gz sim -r -s --render-engine ogre "$ROOT/src/simulation/worlds/soccer.sdf" > "$ROOT/logs/sim-server.log" 2>&1 &
SERVER=$!
gz sim -g --render-engine ogre > "$ROOT/logs/sim-gui.log" 2>&1 &
GUI=$!
cleanup() {
  kill "$GUI" "$SERVER" 2>/dev/null || true
  # Ogre1 may hang while destroying its render thread. Bound shutdown to 3 s.
  for _ in {1..30}; do
    if ! kill -0 "$GUI" 2>/dev/null && ! kill -0 "$SERVER" 2>/dev/null; then break; fi
    sleep .1
  done
  kill -KILL "$GUI" "$SERVER" 2>/dev/null || true
  wait "$GUI" "$SERVER" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
source "$ROOT/.venv/bin/activate"
export PX4_GZ_STANDALONE=1 PX4_GZ_MODEL_NAME=pd_drone PX4_GZ_WORLD=soccer
export PX4_GZ_SIM_RENDER_ENGINE=ogre
# Local SITL has no QGC; retain all estimator checks and offboard loss landing.
export PX4_PARAM_NAV_DLL_ACT=0 PX4_PARAM_COM_OF_LOSS_T=1 PX4_PARAM_COM_OBL_RC_ACT=4
cd "$ROOT/external/PX4-Autopilot"
make -j2 px4_sitl gz_x500
