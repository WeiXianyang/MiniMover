# Repository Guidelines

## Project Structure & Module Organization

This repository contains setup helpers at the root and one ROS 2 simulation package in `wpr_simulation2_src/`. Package manifests and build configuration live in `wpr_simulation2_src/package.xml`, `CMakeLists.txt`, `setup.py`, and `setup.cfg`. Runtime C++/Python nodes are in `src/`, teaching/demo nodes are in `demo_cpp/`, and exercise variants are in `exercises/`. Launch files are split between `launch/` and `demo_launch/`. Simulation assets are grouped by type: `worlds/`, `models/`, `meshes/`, `rviz/`, `config/`, `maps/`, `media/`, and custom messages in `msg/`.

## Build, Test, and Development Commands

Use an Ubuntu ROS 2 environment, preferably Humble as documented in the package README.

- `./setup_ros2_humble.sh`: install or prepare ROS 2 Humble dependencies from the repository root.
- `cd ~/ros2_ws/src && cp -r /path/to/MiniMover/wpr_simulation2_src wpr_simulation2`: place the package in a colcon workspace.
- `cd ~/ros2_ws && colcon build --symlink-install`: build the package and generated messages.
- `source ~/ros2_ws/install/setup.bash`: load the built workspace.
- `ros2 launch wpr_simulation2 wpb_simple.launch.py`: start the simple Gazebo scene.
- `ros2 launch wpr_simulation2 slam.launch.py`: start the SLAM demo.

## Coding Style & Naming Conventions

C++ targets use ROS 2 `rclcpp` conventions with compiler warnings enabled (`-Wall -Wextra -Wpedantic`). Keep C++ source names lowercase with underscores, matching existing files such as `keyboard_vel_cmd.cpp`. Python scripts should be executable ROS nodes and use lowercase snake_case names, such as `face_detector.py`. Launch files should end in `.launch.py` and describe the scenario or robot variant. Use two-space indentation in XML/package metadata and CMake continuation blocks consistent with existing files.

## Testing Guidelines

The package enables `ament_lint_auto` when `BUILD_TESTING` is on, with copyright and cpplint checks currently skipped in `CMakeLists.txt`. Run `colcon test --packages-select wpr_simulation2` after code changes, then inspect results with `colcon test-result --verbose`. For launch or asset changes, verify at least one affected launch file in Gazebo/RViz.

## Commit & Pull Request Guidelines

The current git history only shows `Initial commit`, so no detailed convention is established. Use concise imperative commit messages, for example `Add navigation launch scenario` or `Fix object publisher message type`. Pull requests should include a short summary, affected launch/demo commands, test results, linked issues when available, and screenshots or screen recordings for visual simulation changes.

## Security & Configuration Tips

Do not commit generated build directories (`build/`, `install/`, `log/`) or local credentials. Keep large binary artifacts out of source unless they are required simulation assets.
