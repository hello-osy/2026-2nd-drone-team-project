"""Reproducible simulation-domain YOLO fine tuning; no privileged runtime ball poses.

Analytically render the same white/black sphere over randomized pitch backgrounds.
Labels are generated only for offline training, never used by the flight controller.
"""
from pathlib import Path
import math
import shutil
import json
import hashlib
import cv2
import numpy as np
import torch
from ultralytics import YOLO

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'.cache/datasets/soccer'
rng=np.random.default_rng(42)
phi=(1+math.sqrt(5))/2
axes=np.array([(0,a,b*phi) for a in [-1,1] for b in [-1,1]] +
              [(a,b*phi,0) for a in [-1,1] for b in [-1,1]] +
              [(b*phi,0,a) for a in [-1,1] for b in [-1,1]],dtype=float)
axes/=np.linalg.norm(axes,axis=1)[:,None]

def sample():
    h,w=480,640
    color=np.array([rng.uniform(22,48),rng.uniform(85,125),rng.uniform(20,50)])
    image=np.empty((h,w,3),np.float32);image[:]=color
    stripe=int(rng.integers(120,400));shift=int(rng.integers(stripe))
    for x in range(-shift,w,stripe*2):image[:,max(0,x):min(w,x+stripe)]*=rng.uniform(.65,.95)
    for _ in range(int(rng.integers(0,4))):
        p1=tuple(int(v) for v in rng.integers(-100,740,2))
        p2=tuple(int(v) for v in rng.integers(-100,740,2))
        cv2.line(image,p1,p2,(245,245,245),int(rng.integers(2,9)))
    if rng.random()<.5:
        center=tuple(int(v) for v in rng.integers(-200,700,2))
        radius=int(rng.integers(100,500))
        for a in np.linspace(0,2*math.pi,160):
            x,y=int(center[0]+radius*math.cos(a)),int(center[1]+radius*math.sin(a))
            cv2.rectangle(image,(x-3,y-3),(x+3,y+3),(245,245,245),-1)
    if rng.random()<.12:
        return image.clip(0,255).astype(np.uint8),''
    r=int(rng.integers(8,30));cx=int(rng.integers(r+2,w-r-2));cy=int(rng.integers(r+2,h-r-2))
    yy,xx=np.mgrid[-r:r+1,-r:r+1]/r
    inside=xx*xx+yy*yy<=1
    zz=np.sqrt(np.maximum(0,1-xx*xx-yy*yy))
    normal=np.stack([xx,yy,zz],axis=-1)
    # Random orientation of the actual icosahedral black panel centers.
    q,_=np.linalg.qr(rng.normal(size=(3,3)))
    black=np.max(normal @ (axes@q).T,axis=-1)>.954
    light=np.array([-.3,-.5,1]);light/=np.linalg.norm(light)
    shading=.55+.45*np.maximum(0,normal@light)
    sphere=np.where(black,8.,245.)*shading
    cv2.ellipse(image,(cx+3,cy+3),(r+3,r),0,0,360,tuple((color*.55).tolist()),-1)
    roi=image[cy-r:cy+r+1,cx-r:cx+r+1]
    roi[inside]=np.repeat(sphere[:,:,None],3,axis=2)[inside]
    # Include real Gazebo camera appearance, captured once from our own model.
    # This is offline augmentation, not a color/geometry substitute for YOLO at runtime.
    reference=cv2.imread(str(ROOT/'models/ball-reference.png'))
    if reference is not None and rng.random()<.8:
        reference=cv2.rotate(reference,int(rng.choice([cv2.ROTATE_90_CLOCKWISE,cv2.ROTATE_180,cv2.ROTATE_90_COUNTERCLOCKWISE])))
        reference=cv2.resize(reference,(2*r+1,2*r+1),interpolation=cv2.INTER_LINEAR)
        roi[inside]=reference[inside]
    image+=rng.normal(0,1.2,image.shape)
    if rng.random()<.3:image=cv2.GaussianBlur(image,(3,3),.6)
    return image.clip(0,255).astype(np.uint8),f'0 {cx/w} {cy/h} {(2*r+2)/w} {(2*r+2)/h}\n'

def main():
    torch.set_num_threads(2)
    for split,count in [('train',128),('val',32)]:
        for folder in ['images','labels']:(DATA/folder/split).mkdir(parents=True,exist_ok=True)
        for i in range(count):
            image,label=sample()
            cv2.imwrite(str(DATA/'images'/split/f'{i:04d}.jpg'),image)
            (DATA/'labels'/split/f'{i:04d}.txt').write_text(label)
    config=DATA/'data.yaml'
    config.write_text(f'path: {DATA}\ntrain: images/train\nval: images/val\nnames:\n  0: soccer ball\n')
    YOLO(str(ROOT/'models/yolo11n.pt')).train(data=str(config),device='cpu',
        epochs=16,imgsz=320,batch=8,workers=0,freeze=10,optimizer='AdamW',lr0=.002,
        project=str(ROOT/'.cache/training'),name='soccer',exist_ok=True,
        pretrained=True,plots=False,cache=False,amp=False,seed=42,
        mosaic=0.,mixup=0.,degrees=10,translate=.05,scale=.2,fliplr=.5,
        hsv_h=.015,hsv_s=.2,hsv_v=.2)
    shutil.copy2(ROOT/'.cache/training/soccer/weights/best.pt',ROOT/'models/soccer_yolo.pt')
    weights=ROOT/'models/soccer_yolo.pt'
    (ROOT/'models/model-info.json').write_text(json.dumps({
        'base':'YOLO11n','runtime':'PyTorch 2.8.0 CPU','classes':['soccer ball'],
        'training':'128 training / 32 validation synthetic images; own Gazebo ball reference',
        'seed':42,'epochs':16,'imgsz':320,
        'sha256':hashlib.sha256(weights.read_bytes()).hexdigest(),
        'scope':'Simulation-specific; real football footage not validated'},indent=2)+'\n')

if __name__=='__main__':main()
