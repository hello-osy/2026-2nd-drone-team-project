"""Capture actual ROS camera frames for diagnosis (no flight commands)."""
import time
from pathlib import Path
import cv2
import rclpy
from pd_drone.app import Cameras, State

state=State()
rclpy.init(); node=Cameras(state)
deadline=time.monotonic()+15
while len(state.frames)<2 and time.monotonic()<deadline:
    rclpy.spin_once(node,timeout_sec=.5)
for name,(_,frame) in state.frames.items():
    path=Path('logs')/f'{name}.png'
    cv2.imwrite(str(path),frame)
    print(path)
node.destroy_node(); rclpy.shutdown()
if len(state.frames)!=2:
    raise SystemExit('Missing camera stream')
