#!/usr/bin/env bash
# Ubuntu 24.04: recover every ignored dependency from a plain project checkout.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT=$PWD
source configs/sources.env
JOBS=${BUILD_JOBS:-2}
MODE=${1:-}
case "$MODE" in
  --check) exec /usr/bin/python3 src/pd_drone/check_environment.py ;;
  ''|--skip-system) ;;
  *) echo 'Usage: bash setup.sh [--check|--skip-system]'; exit 2 ;;
esac
[[ $JOBS =~ ^[1-9][0-9]*$ ]] || { echo 'BUILD_JOBS must be a positive integer'; exit 2; }
if (( EUID == 0 )); then echo 'Run as your normal user: bash setup.sh (sudo is requested only for apt).'; exit 1; fi
source /etc/os-release
[[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 ]] || { echo 'Ubuntu 24.04 is required.'; exit 1; }
case "$(uname -m)" in aarch64|x86_64) ;; *) echo 'Only ARM64 / AMD64 are supported.'; exit 1 ;; esac
trap 'echo "Setup stopped at line $LINENO. Fix the error and rerun bash setup.sh." >&2' ERR

# Do not inherit a different ROS distribution, Python virtualenv or DDS library path.
unset VIRTUAL_ENV PYTHONHOME PYTHONPATH AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH LD_LIBRARY_PATH
export PATH="/usr/bin:/bin:$PATH"
export PIP_CACHE_DIR="$ROOT/.cache/pip" CCACHE_DIR="$ROOT/.cache/ccache"
export YOLO_CONFIG_DIR="$ROOT/.cache/ultralytics"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
export CMAKE_BUILD_PARALLEL_LEVEL="$JOBS"
mkdir -p external/ros2_ws/src external/build downloads logs recordings "$PIP_CACHE_DIR" "$CCACHE_DIR" "$YOLO_CONFIG_DIR"

if [[ $MODE != --skip-system ]]; then
  echo '[1/7] Ubuntu, ROS 2 Jazzy and Gazebo Harmonic'
  sudo -v
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl git gnupg lsb-release locales software-properties-common python3
  sudo add-apt-repository -y universe
  sudo locale-gen en_US.UTF-8
  if ! dpkg-query -W -f='${Status}' ros2-apt-source 2>/dev/null | grep -q 'install ok installed'; then
    curl -fL --retry 3 \
      "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.noble_all.deb" \
      -o downloads/ros2-apt-source.deb
    sudo dpkg -i downloads/ros2-apt-source.deb
  fi
  curl -fsSL --retry 3 https://packages.osrfoundation.org/gazebo.gpg -o downloads/gazebo.gpg
  sudo install -m 644 downloads/gazebo.gpg /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable noble main" \
    | sudo tee /etc/apt/sources.list.d/gazebo-stable.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y \
    build-essential cmake ninja-build pkg-config astyle ccache cppcheck file gdb lcov \
    libssl-dev libxml2-dev libxml2-utils libeigen3-dev libunwind-dev cppzmq-dev \
    libasio-dev libtinyxml2-dev libopencv-dev libimage-exiftool-perl protobuf-compiler \
    rsync shellcheck unzip zip bc wget \
    python3-dev python3-pip python3-venv python3-setuptools python3-wheel \
    python3-gi python3-numpy python3-opencv \
    gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav \
    ros-jazzy-desktop ros-dev-tools ros-jazzy-ros-gz-bridge gz-harmonic libgz-sim8-dev
fi
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

ensure_repo() {
  local url=$1 dest=$2 ref=$3 commit=$4
  if [[ ! -d $dest/.git && ! -f $dest/.git ]]; then
    [[ ! -e $dest ]] || { echo "Not an empty repository destination: $dest"; return 1; }
    git clone --depth 1 --no-checkout --branch "$ref" "$url" "$dest"
    git -C "$dest" cat-file -e "$commit^{commit}" 2>/dev/null || git -C "$dest" fetch --depth 1 origin "$commit"
    git -C "$dest" checkout --detach "$commit"
  else
    [[ $(git -C "$dest" rev-parse HEAD) == "$commit" ]] || { echo "Revision differs in $dest. Preserve your changes and move that folder aside before retrying."; return 1; }
    [[ -z $(git -C "$dest" status --porcelain --untracked-files=no) ]] || { echo "Tracked changes in $dest; setup will not overwrite them."; return 1; }
  fi
  git -C "$dest" submodule update --init --recursive --depth 1
}
echo '[2/7] Restore pinned external repositories'
ensure_repo https://github.com/PX4/PX4-Autopilot.git external/PX4-Autopilot "$PX4_REF" "$PX4_COMMIT"
ensure_repo https://github.com/eProsima/Micro-XRCE-DDS-Agent.git external/Micro-XRCE-DDS-Agent "$DDS_AGENT_REF" "$DDS_AGENT_COMMIT"
ensure_repo https://github.com/PX4/px4_msgs.git external/ros2_ws/src/px4_msgs "$PX4_MSGS_REF" "$PX4_MSGS_COMMIT"

echo '[3/7] Project Python environment (CPU-only PyTorch)'
[[ -x .venv/bin/python ]] || /usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -c configs/px4-constraints.txt \
  -r external/PX4-Autopilot/Tools/setup/requirements.txt -r configs/requirements.txt

echo '[4/7] PX4 SITL'
source .venv/bin/activate
make -C external/PX4-Autopilot -j"$JOBS" px4_sitl
deactivate

echo '[5/7] DDS Agent (local prefix, no sudo make install)'
cmake -S external/Micro-XRCE-DDS-Agent -B external/Micro-XRCE-DDS-Agent/build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$ROOT/external/dds-agent-install"
cmake --build external/Micro-XRCE-DDS-Agent/build --parallel "$JOBS"
cmake --install external/Micro-XRCE-DDS-Agent/build

echo '[6/7] ROS workspace and soccer simulation'
(
  set +u
  source /opt/ros/jazzy/setup.bash
  cd "$ROOT/external/ros2_ws"
  colcon build --base-paths src --symlink-install --executor sequential \
    --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3 -DPYTHON_EXECUTABLE=/usr/bin/python3 -DCMAKE_BUILD_TYPE=Release
)
/usr/bin/python3 src/pd_drone/generate_scene.py
cmake -S src/simulation/plugins -B external/build/pd_ball -DCMAKE_BUILD_TYPE=Release
cmake --build external/build/pd_ball --parallel "$JOBS"

echo '[7/7] Model files and environment checks'
if [[ ! -f models/yolo11n.pt ]]; then
  (cd models; "$ROOT/.venv/bin/python" -c 'from ultralytics import YOLO; YOLO("yolo11n.pt")')
fi
if [[ ! -f models/soccer_yolo.pt ]]; then
  bash scripts/train.sh
fi
/usr/bin/python3 src/pd_drone/check_environment.py
echo 'Setup complete. Run the four terminal commands in README.md.'
