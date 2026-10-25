# Soccer PD Drone

Ubuntu 24.04 ARM64 · PX4 v1.16 · ROS 2 Jazzy · Gazebo Harmonic(Ogre1).
고정 축구장과 움직이는 공, 전방(+X)·하방(−Z) 카메라, **CPU YOLO 자동 추적 + 브라우저 영상 중계**.

## 환경 세팅

```bash
cd /home/osy/OSY_STUDY/drone_team_project
bash setup.sh
```

새로 클론한 환경에서도 ROS·Gazebo·PX4·DDS Agent·가상환경·빌드를 자동 구성한다. 인터넷/sudo 필요.
`external/`, `.venv/`, 캐시·로그는 Git 제외, **모델 가중치는 Git 포함**. 설치 확인: `bash setup.sh --check`.

## 실행

터미널마다 프로젝트 폴더로 이동한 뒤 각각 실행:

```bash
cd /home/osy/OSY_STUDY/drone_team_project
```

```bash
# 터미널 1: 축구장 + 공 + 드론 + PX4
bash scripts/sim.sh
```
```bash
# 터미널 2: DDS Agent
bash scripts/agent.sh
```
```bash
# 터미널 3: 카메라 브리지
bash scripts/bridge.sh
```
```bash
# 터미널 4: 자동 이륙 + CPU YOLO 추적 + 중계
bash scripts/track.sh --fly
```

영상: **http://127.0.0.1:8080** (Ubuntu VM 내부). `--fly`를 빼면 영상·탐지만 실행.
추적 터미널에서 `Ctrl+C` → 착륙 확인 → 나머지 종료. 새 비행은 시뮬레이션부터 재시작.
**로컬 시뮬레이션 전용이며 실사 경기 성능은 미검증.**

구조: `external/` 외부 코드 · `configs/` 설정 · `models/` 가중치 · `scripts/` 실행 · `src/` 구현 · `docs/` 문서.
[설치·복구 상세](docs/setup.md) · [동작·검증](docs/operation.md) · [외부 라이선스](docs/third-party.md)
