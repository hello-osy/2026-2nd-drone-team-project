"""Read-only setup audit: binaries, pinned sources, Python imports and model hash."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
failures=[]

def check(name, action):
    try:
        action()
        print(f'OK   {name}',flush=True)
    except Exception as exc:
        failures.append(name)
        print(f'FAIL {name}: {exc}',flush=True)

def command(args, env=None, success_codes=(0,)):
    result=subprocess.run(args,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
    if result.returncode not in success_codes:
        raise RuntimeError(result.stdout[-1200:])
    return result.stdout.strip()

def require(path):
    if not (ROOT/path).is_file(): raise FileNotFoundError(path)

def revision(path, expected):
    actual=command(['git','-C',path,'rev-parse','HEAD'])
    if actual!=expected: raise RuntimeError(f'{actual} != {expected}')

def weights():
    require('models/yolo11n.pt')
    p=ROOT/'models/soccer_yolo.pt'
    info=json.loads((ROOT/'models/model-info.json').read_text())
    if hashlib.sha256(p.read_bytes()).hexdigest()!=info['sha256']:
        raise RuntimeError('soccer_yolo.pt checksum differs from model-info.json')

def agent():
    env=dict(os.environ,LD_LIBRARY_PATH=f'{ROOT}/external/dds-agent-install/lib:{ROOT}/external/dds-agent-install/lib64')
    # Agent 2.4.3 intentionally returns 1 for --help, even when installed correctly.
    output=command([str(ROOT/'external/dds-agent-install/bin/MicroXRCEAgent'),'--help'],env,(0,1))
    if "Usage: 'MicroXRCEAgent" not in output:
        raise RuntimeError(output[-1000:])

def main():
    versions=dict(line.split('=',1) for line in (ROOT/'configs/sources.env').read_text().splitlines() if line and not line.startswith('#'))
    for path,key in [('external/PX4-Autopilot','PX4_COMMIT'),
                     ('external/Micro-XRCE-DDS-Agent','DDS_AGENT_COMMIT'),
                     ('external/ros2_ws/src/px4_msgs','PX4_MSGS_COMMIT')]:
        check(path,lambda p=path,k=key:revision(p,versions[k]))
    check('PX4 SITL binary',lambda:require('external/PX4-Autopilot/build/px4_sitl_default/bin/px4'))
    check('Gazebo Harmonic',lambda:command(['gz','sim','--versions']))
    check('Soccer plugin',lambda:require('external/build/pd_ball/libpd_ball.so'))
    check('Soccer world',lambda:require('src/simulation/worlds/soccer.sdf'))
    check('DDS Agent',agent)
    check('Python / CPU YOLO',lambda:command([str(ROOT/'.venv/bin/python'),'-c',
        'import cv2,numpy,torch,ultralytics,mavsdk; assert torch.version.cuda is None; assert numpy.__version__.startswith("1.")']))
    check('ROS / px4_msgs / image bridge',lambda:command(['bash','-c',
        'set -e; source /opt/ros/jazzy/setup.bash; source "$1/external/ros2_ws/install/setup.bash"; '
        'ros2 pkg prefix ros_gz_bridge; /usr/bin/python3 -c "import rclpy; from px4_msgs.msg import SensorCombined"',
        'check',str(ROOT)]))
    check('Versioned model weights',weights)
    if failures:
        print('Run: bash setup.sh')
        return 1
    print('Environment ready.')
    return 0

if __name__=='__main__':
    sys.exit(main())
