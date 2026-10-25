"""ROS camera ingress -> CPU YOLO -> MAVSDK velocity control + local MJPEG."""
import argparse
import asyncio
import json
import threading
import time
import subprocess
from importlib.resources import files
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from mavsdk import System
from mavsdk.offboard import VelocityBodyYawspeed
from ultralytics import YOLO
import torch
from pd_drone.control import velocity, fresh

ROOT = Path(__file__).resolve().parents[2]

class SitlSystem(System):
    # Close explicitly while Python is still alive, rather than from __del__.
    def __del__(self):
        pass

    @staticmethod
    def _start_mavsdk_server(system_address, port, sysid, compid):
        executable=files('mavsdk').joinpath('bin/mavsdk_server')
        (ROOT/'logs').mkdir(exist_ok=True)
        with (ROOT/'logs/mavsdk.log').open('w') as log:
            return subprocess.Popen([str(executable),'-p',str(port),
                '--sysid',str(sysid),'--compid',str(compid),system_address],
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)

    def _stop_mavsdk_server(self):
        process=self._server_process
        self._server_process=None
        if process is not None:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()

class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.frames = {}
        self.jpeg = {}
        self.target = None
        self.target_at = 0.
        self.error = None
        self.mode = 'STARTING'
        self.ball_run = False
        self.detections = 0
        self.inference_ms = 0.
        self.position = {}
        self.stop = threading.Event()

class Cameras(Node):
    def __init__(self, state):
        super().__init__('soccer_pd_cameras')
        self.state = state
        self.ball_pub = self.create_publisher(Bool, '/pd/ball/run', 1)
        self.create_timer(.5, lambda: self.ball_pub.publish(Bool(data=state.ball_run)))
        for camera in ['front', 'down']:
            self.create_subscription(Image, f'/pd/{camera}/image',
                lambda msg, c=camera: self.receive(c, msg), qos_profile_sensor_data)

    def receive(self, camera, msg):
        channels = {'rgb8':3, 'bgr8':3, 'rgba8':4, 'bgra8':4}.get(msg.encoding)
        if channels is None:
            self.state.error = f'Unsupported image encoding: {msg.encoding}'
            return
        try:
            rows = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.step)
            frame = rows[:, :msg.width*channels].reshape(msg.height, msg.width, channels)
            if msg.encoding == 'rgb8':
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            elif msg.encoding == 'rgba8':
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            elif msg.encoding == 'bgra8':
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            with self.state.lock:
                self.state.frames[camera] = (time.monotonic(), frame.copy())
        except Exception as exc:
            self.state.error = f'Image decode failed: {exc}'

def vision(state, args):
    try:
        torch.set_num_threads(args.threads)
        detector = YOLO(str(args.weights))
        ball_classes = [k for k,v in detector.names.items() if v in ('sports ball', 'ball', 'soccer ball')]
        if not ball_classes:
            raise ValueError('Weights must contain sports ball / ball / soccer ball class')
        last = {}
        while not state.stop.is_set():
            with state.lock:
                frames = dict(state.frames)
            for camera, (stamp, source) in frames.items():
                if last.get(camera) == stamp:
                    continue
                last[camera] = stamp
                frame = source.copy()
                if camera == 'down':
                    result = detector.predict(frame, device='cpu', imgsz=args.imgsz,
                        classes=ball_classes, conf=args.conf, verbose=False)[0]
                    target = None
                    if len(result.boxes):
                        box = result.boxes[int(result.boxes.conf.argmax())]
                        x1,y1,x2,y2 = box.xyxy[0].cpu().tolist()
                        target = ((x1+x2)/2, (y1+y2)/2)
                        cv2.rectangle(frame,(int(x1),int(y1)),(int(x2),int(y2)),(0,230,255),2)
                        cv2.putText(frame,f'ball {float(box.conf[0]):.2f}',
                            (int(x1),max(20,int(y1)-6)),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,230,255),1)
                    with state.lock:
                        state.target = target
                        state.inference_ms = round(result.speed['inference'],1)
                        if target is not None: state.detections += 1
                        # Use receipt time, not inference completion: slow inference must not command stale motion.
                        state.target_at = stamp if target else 0.
                cv2.putText(frame, f'{camera.upper()} | {state.mode}', (12,24),
                    cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),2)
                ok, jpeg = cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,80])
                if ok:
                    with state.lock:
                        state.jpeg[camera] = (stamp,jpeg.tobytes())
            state.stop.wait(.02)
    except Exception as exc:
        state.error = f'YOLO failed: {exc}'

def serve(state, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            if self.path == '/':
                body = b'''<!doctype html><meta charset="utf-8"><title>Soccer PD</title>
<style>body{background:#101b25;color:white;font-family:sans-serif;margin:24px}img{width:48%;max-width:640px}a{color:#7dd}</style>
<h1>Soccer PD LIVE</h1><p>Front (+X) / Down (-Z), CPU YOLO overlay</p>
<img src="/front.mjpg"><img src="/down.mjpg"><p id="status"></p>
<script>setInterval(async()=>{try{let s=await(await fetch('/health')).json();document.querySelector('#status').textContent=JSON.stringify(s)}catch(e){document.querySelector('#status').textContent='DISCONNECTED'}},1000)</script>'''
                self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
                self.end_headers(); self.wfile.write(body)
            elif self.path == '/health':
                with state.lock:
                    ages = {k:round(time.monotonic()-v[0],2) for k,v in state.frames.items()}
                body = json.dumps({'mode':state.mode,'camera_age_seconds':ages,
                    'detections':state.detections,'inference_ms':state.inference_ms,
                    'position_ned':state.position,'error':state.error}).encode()
                self.send_response(200); self.send_header('Content-Type','application/json')
                self.end_headers(); self.wfile.write(body)
            elif self.path in ('/front.mjpg','/down.mjpg'):
                camera = self.path[1:].split('.')[0]
                self.send_response(200)
                self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame')
                self.send_header('Cache-Control','no-store'); self.end_headers()
                try:
                    while not state.stop.is_set():
                        with state.lock:
                            data = state.jpeg.get(camera)
                        if data and time.monotonic()-data[0] < 2:
                            jpeg = data[1]
                        else:
                            img = np.zeros((480,640,3),np.uint8)
                            cv2.putText(img,'WAITING / STALE VIDEO',(35,240),0,.8,(0,100,255),2)
                            jpeg = cv2.imencode('.jpg',img)[1].tobytes()
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(jpeg)).encode()+b'\r\n\r\n'+jpeg+b'\r\n')
                        state.stop.wait(.1)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_error(404)
    server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server

async def first_matching(stream, predicate, timeout=45):
    async def wait():
        async for value in stream:
            if predicate(value):
                return value
    return await asyncio.wait_for(wait(),timeout)

async def flight(state, args):
    drone = SitlSystem()
    armed = False
    monitor = None
    latest = {'at':0., 'north':0.,'east':0.,'alt':0.}
    async def telemetry():
        async for pv in drone.telemetry.position_velocity_ned():
            latest.update(at=time.monotonic(),north=pv.position.north_m,
                          east=pv.position.east_m,alt=-pv.position.down_m)
            state.position={k:round(v,2) for k,v in latest.items() if k!='at'}
    try:
        state.mode = 'CONNECTING'
        await asyncio.wait_for(drone.connect(system_address='udpin://0.0.0.0:14540'),15)
        await first_matching(drone.core.connection_state(),lambda v:v.is_connected)
        await first_matching(drone.telemetry.health(),lambda h:h.is_global_position_ok and h.is_home_position_ok)
        await drone.action.hold()
        await first_matching(drone.telemetry.health(),lambda h:h.is_armable)
        monitor = asyncio.create_task(telemetry())
        deadline=time.monotonic()+30
        while True:
            if state.error:
                raise RuntimeError(state.error)
            with state.lock:
                ready = 'down' in state.jpeg and all(
                    c in state.frames and fresh(state.frames[c][0],time.monotonic(),2)
                    for c in ['front','down'])
            if ready: break
            if time.monotonic()>deadline: raise TimeoutError('Both camera streams and YOLO must be ready before takeoff')
            await asyncio.sleep(.1)
        state.mode='TAKEOFF'
        await drone.action.set_takeoff_altitude(args.altitude)
        await drone.action.arm(); armed=True
        await drone.action.takeoff()
        await first_matching(drone.telemetry.position(),lambda p:p.relative_altitude_m>args.altitude-.5,60)
        await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0,0,0,0))
        await drone.offboard.start()
        last_seen=time.monotonic()
        while not state.stop.is_set():
            now=time.monotonic()
            if state.error: raise RuntimeError(state.error)
            if not fresh(latest['at'],now,2): raise RuntimeError('Telemetry timeout')
            if abs(latest['north'])>8 or abs(latest['east'])>12 or latest['alt']>8:
                raise RuntimeError('Simulation flight boundary reached')
            with state.lock:
                target=state.target if fresh(state.target_at,now) else None
                frame=state.frames.get('down')
            if target is not None:
                last_seen=now
                state.mode='TRACKING'
                state.ball_run=True
            else:
                state.mode='SEARCH / HOLD'
            if now-last_seen>12: raise RuntimeError('Ball lost for 12 seconds; landing')
            h,w=frame[1].shape[:2] if frame else (480,640)
            f,r=velocity(target,w,h,max(1,latest['alt']))
            down=max(-.4,min(.4,.6*(latest['alt']-args.altitude)))
            await drone.offboard.set_velocity_body(VelocityBodyYawspeed(f,r,down,0))
            await asyncio.sleep(.05)
    finally:
        state.ball_run=False
        if armed:
            state.mode='LANDING'
            try:
                await asyncio.wait_for(drone.action.land(),8)
                await first_matching(drone.telemetry.in_air(),lambda x:not x,60)
                state.mode='LANDED'
                print('Landing confirmed.',flush=True)
            except Exception as exc:
                state.mode='LAND COMMAND FAILED'
                print(f'Landing not confirmed: {exc}; use PX4 commander land',flush=True)
        if monitor:
            monitor.cancel()
            await asyncio.gather(monitor,return_exceptions=True)
        # MAVSDK 3.x owns a server process with a non-daemon output thread.
        drone._stop_mavsdk_server()

async def run(args, state):
    if args.fly:
        await flight(state,args)
    else:
        state.mode='PREVIEW'
        while not state.stop.is_set():
            if state.error: raise RuntimeError(state.error)
            await asyncio.sleep(.2)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fly',action='store_true',help='SITL only: arm, take off, track, land on loss/exit')
    parser.add_argument('--weights',type=Path,default=ROOT/'models/soccer_yolo.pt')
    parser.add_argument('--altitude',type=float,default=4.)
    parser.add_argument('--conf',type=float,default=.25)
    parser.add_argument('--imgsz',type=int,default=320)
    parser.add_argument('--threads',type=int,default=2)
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args()
    if not args.weights.is_file(): parser.error('Model missing; run bash setup.sh')
    if not 2 <= args.altitude <= 6: parser.error('Altitude must be 2..6 m for this simulation')
    state=State()
    rclpy.init(); node=Cameras(state)
    threading.Thread(target=rclpy.spin,args=(node,),daemon=True).start()
    threading.Thread(target=vision,args=(state,args),daemon=True).start()
    server=serve(state,args.port)
    print(f'Broadcast: http://127.0.0.1:{args.port} | fly={args.fly}',flush=True)
    try:
        asyncio.run(run(args,state))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f'Stopped: {type(exc).__name__}: {exc}',flush=True)
        raise SystemExit(1)
    finally:
        state.stop.set(); server.shutdown(); rclpy.shutdown()

if __name__=='__main__':
    main()
