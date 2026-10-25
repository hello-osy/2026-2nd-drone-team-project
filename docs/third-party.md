# 외부 구성요소

- [PX4 Autopilot](https://github.com/PX4/PX4-Autopilot): BSD-3-Clause. 기체 모델은 PX4 x500을 기반으로 생성하며 원본·메시지는 고정 커밋으로 내려받는다.
- [Micro XRCE-DDS Agent](https://github.com/eProsima/Micro-XRCE-DDS-Agent): Apache-2.0.
- [Ultralytics](https://github.com/ultralytics/ultralytics): AGPL-3.0 또는 별도 Enterprise 라이선스. 포함한 YOLO11n 기본·파생 가중치에도 해당 조건을 확인해야 한다.
- [PyTorch](https://github.com/pytorch/pytorch): BSD 계열 라이선스. CPU 배포본 사용.
- [ROS 2](https://github.com/ros2)와 [Gazebo](https://github.com/gazebosim): 각 패키지의 원본 라이선스 적용.

`models/ball-reference.png`는 이 프로젝트에서 만든 Gazebo 공을 직접 캡처한 학습 참조 이미지다. `models/model-info.json`에는 보정 조건과 가중치 SHA-256을 기록한다. 외부 코드의 원본 라이선스는 내려받은 각 저장소에 보존된다.
