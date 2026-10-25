# 동작과 검증

- 30×20 m 고정 연습장, 지정 경로로 움직이는 축구공. 실제 경기 물리 모델은 아니다.
- 카메라 두 개: 기체 +X 전방, −Z 하방. 각 640×480 / 시뮬레이션 10 Hz.
- `Gazebo → ros_gz_bridge → rclpy → CPU YOLO → MAVSDK 속도 제어`.
- DDS Agent는 PX4의 ROS 토픽을 연결한다. 추적 비행 명령은 MAVSDK/MAVLink를 사용한다.
- 추적기는 공의 실제 위치를 읽지 않는다. 공 이동 시작/초기화 Bool 신호만 송신한다.
- YOLO11n을 자체 합성 데이터와 자체 Gazebo 공 이미지로 보정했다. 실사 경기 성능은 검증하지 않았다.
- 브라우저 중계는 VM 내부 `127.0.0.1:8080`의 MJPEG이며 외부 방송 서비스 업로드는 포함하지 않는다.

비행 고도 기본 4 m, 수평 최대 0.7 m/s. 탐지 지연 0.8초 초과 시 수평 정지, 미탐지 12초 시 착륙한다. 위치 범위는 홈 기준 북/남 8 m, 동/서 12 m 이내다. Ctrl+C는 착륙을 요청하고 확인한 뒤 종료한다. PX4 자체 Offboard 연결 상실 동작도 착륙으로 설정한다. 이 설정은 로컬 SITL 전용이다.

```bash
bash scripts/track.sh                               # 비행 없이 영상·탐지
bash scripts/track.sh --fly --altitude 3             # 자동 비행 고도 변경 (2~6 m)
bash scripts/track.sh --fly --weights models/soccer_yolo.pt
bash scripts/capture.sh                             # logs/에 두 카메라 PNG
bash scripts/verify.sh                              # 실행 중인 추적을 60초 관찰
PYTHONPATH=src .venv/bin/python -m unittest discover -s src/tests
```

오류 로그: `logs/sim-server.log`, `logs/sim-gui.log`, `logs/mavsdk.log`.
새 비행은 시뮬레이션부터 재시작해 공과 드론의 위치를 초기화한다. 모든 터미널을 한꺼번에 닫지 말고 추적기 착륙 확인 후 나머지를 종료한다.

2026-10-25 ARM64/UTM 검증: 60초 동안 20/20 관찰에서 TRACKING, 시작점 대비 최대 이동 약 6 m, CPU 추론 평균 약 101 ms. 두 영상 수신 및 Ctrl+C 착륙 확인. 이는 해당 시나리오 관찰값이며 실경기 정확도나 FPS 보장은 아니다.
