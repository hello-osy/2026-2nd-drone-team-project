#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
export LD_LIBRARY_PATH="$PWD/external/dds-agent-install/lib:$PWD/external/dds-agent-install/lib64"
exec ./external/dds-agent-install/bin/MicroXRCEAgent udp4 -p 8888
