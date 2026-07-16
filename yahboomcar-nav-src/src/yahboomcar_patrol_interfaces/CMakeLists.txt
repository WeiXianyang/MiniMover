cmake_minimum_required(VERSION 3.5)
project(yahboomcar_patrol_interfaces)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/SetRoute.srv"
  "srv/GetRoute.srv"
  "srv/GetRobotPose.srv"
  DEPENDENCIES geometry_msgs nav_msgs
)

ament_package()
