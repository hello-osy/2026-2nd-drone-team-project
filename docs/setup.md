# 환경 복구와 폴더 구조

`bash setup.sh`는 Ubuntu 24.04에서 다음 순서로 설치한다. 실제 검증 환경은 ARM64/UTM이며 AMD64 분기도 제공한다.

1. 시스템 패키지, ROS 2 Jazzy 저장소·Desktop·카메라 브리지, Gazebo Harmonic.
2. `configs/sources.env`의 커밋으로 PX4, Micro XRCE-DDS Agent, px4_msgs 복원.
3. `.venv`와 CPU 전용 PyTorch, MAVSDK, YOLO, PX4 Python 의존성 설치.
4. PX4 SITL, 프로젝트 내부 DDS Agent, ROS 작업 공간, 공 이동 플러그인 빌드.
5. 모델 및 Python/ROS/실행 파일 검사.

인터넷과 sudo 권한이 필요하다. 전체 설치는 다운로드·소스 빌드 때문에 오래 걸릴 수 있다. apt 패키지는 `/usr`와 `/opt/ros/jazzy` 등 시스템 경로에 설치되고, 프로젝트 의존성은 이 폴더 안에 저장된다. `.bashrc`는 수정하지 않는다.

```bash
bash setup.sh                 # 새 환경 설치 / 중단된 설치 재시도
bash setup.sh --check         # 설치 상태만 검사 (sudo/다운로드 없음)
bash setup.sh --skip-system   # apt 설치가 끝난 환경의 프로젝트 의존성만 복구
BUILD_JOBS=1 bash setup.sh    # 메모리가 부족한 VM
```

기존 외부 저장소의 커밋이 다르거나 수정된 파일이 있으면 덮어쓰지 않고 중단한다. 해당 작업을 보존한 뒤 폴더를 다른 곳으로 옮기고 재실행한다. 프로젝트 자체를 다른 경로로 옮겼다면 절대 경로를 저장하는 `.venv` 및 외부 빌드 디렉터리도 새로 생성해야 한다.

```text
setup.sh                  전체 환경 설치·복구 진입점
external/                 외부 저장소·ROS 작업 공간·빌드·Agent 설치 결과 (Git 제외)
  PX4-Autopilot/
  Micro-XRCE-DDS-Agent/
  dds-agent-install/
  ros2_ws/src/px4_msgs/
  build/pd_ball/
configs/                  의존성 버전·외부 저장소 커밋
models/                   추적 가중치·기본 가중치·공 참조 이미지·메타데이터 (Git 포함)
scripts/                  사용자가 실행하는 셸 명령
src/pd_drone/             추적·송출·학습·환경 검사 구현
src/simulation/           월드·기체 SDF·Gazebo 플러그인 소스
src/tests/                제어 테스트
docs/                     추가 설명
.venv/ .cache/            Python 환경·학습 데이터·캐시 (Git 제외)
logs/ recordings/         실행 산출물 (Git 제외)
```

ROS 작업 공간 활성화:

```bash
source /opt/ros/jazzy/setup.bash
source external/ros2_ws/install/setup.bash
```

`models/soccer_yolo.pt`와 `models/yolo11n.pt`는 각각 약 5 MB여서 일반 Git으로 관리한다. 학습 데이터·중간 체크포인트는 `.cache/`에만 생성된다. 가중치가 없으면 설치기가 기본 모델 다운로드 및 CPU 보정 학습을 수행한다. 직접 다시 학습할 때는 `bash scripts/train.sh`를 사용하며, 결과 가중치와 `model-info.json`을 함께 커밋한다.
