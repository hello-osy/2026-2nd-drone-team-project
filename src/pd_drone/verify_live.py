"""Observe an already running simulation for 60 s; never sends flight commands."""
import json
import math
import time
import urllib.request
from pathlib import Path

opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
samples=[]
for _ in range(20):
    try:
        with opener.open('http://127.0.0.1:8080/health',timeout=5) as response:
            sample=json.load(response)
    except Exception as exc:
        print('Server stopped:',exc,flush=True)
        break
    samples.append(sample)
    print(sample,flush=True)
    if sample['mode']=='TRACKING':
        for camera in ['front','down']:
            with opener.open(f'http://127.0.0.1:8080/{camera}.mjpg',timeout=5) as response:
                data=b''
                while b'\xff\xd9' not in data:
                    data+=response.read(1024)
                start=data.index(b'\xff\xd8');end=data.index(b'\xff\xd9',start)+2
                Path(f'logs/verified-{camera}.jpg').write_bytes(data[start:end])
    time.sleep(3)
positions=[s['position_ned'] for s in samples if s['position_ned']]
travel=max((math.hypot(p['north']-positions[0]['north'],p['east']-positions[0]['east']) for p in positions),default=0)
tracking=sum(s['mode']=='TRACKING' for s in samples)
result={'samples':samples,'tracking_samples':tracking,'displacement_m':travel,
        'passed':len(samples)==20 and tracking>=10 and travel>.5 and all(s['error'] is None for s in samples)}
Path('logs/integration.json').write_text(json.dumps(result,indent=2))
print('RESULT',tracking,travel,result['passed'])
raise SystemExit(0 if result['passed'] else 1)
