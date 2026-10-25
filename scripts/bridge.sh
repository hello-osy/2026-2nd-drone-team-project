#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0
exec ros2 run ros_gz_bridge parameter_bridge \
  '/pd/front/image@sensor_msgs/msg/Image[gz.msgs.Image' \
  '/pd/down/image@sensor_msgs/msg/Image[gz.msgs.Image' \
  '/pd/ball/run@std_msgs/msg/Bool]gz.msgs.Boolean' \
  --ros-args -p qos_profile:=SENSOR_DATA
