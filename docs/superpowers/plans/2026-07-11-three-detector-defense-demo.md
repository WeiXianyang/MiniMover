# Three Detector Defense Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a double-click Windows launcher that opens three independent looping recognition-demo windows and include a compact combined MP4 fallback, then merge the completed branch into `main`.

**Architecture:** A small OpenCV player reads pre-generated MP4 files from `demo_showcase/videos/`. A build script converts copied, provenance-labelled result images into short animated clips and a 3-panel combined fallback. The root BAT performs dependency checks and launches three independent Python processes with relative paths.

**Tech Stack:** Python 3, OpenCV, NumPy, `unittest`, Windows Batch, Git LFS.

---

## File structure

- `demo_showcase/player.py`: reusable looping OpenCV video player with title and window-position arguments.
- `demo_showcase/build_videos.py`: deterministic clip/composite generator.
- `demo_showcase/assets/*.jpg`: copied source/result frames used to rebuild videos.
- `demo_showcase/videos/*.mp4`: three short clips plus one combined fallback.
- `demo_showcase/tests/test_demo_showcase.py`: tests for path resolution, argument parsing, frame composition and asset validation.
- `demo_showcase/README.md`: five-minute defense instructions and fallback steps.
- `一键启动三项识别演示.bat`: root entry point that launches three processes concurrently.

### Task 1: Define and test demo interfaces

**Files:**
- Create: `demo_showcase/tests/test_demo_showcase.py`
- Create: `demo_showcase/__init__.py`

- [ ] Write tests that import the wished-for `player` and `build_videos` APIs and assert: repository-relative video resolution, missing-file reporting, exactly three module definitions, output frame size `640x360`, and CLI defaults.
- [ ] Run `python -m unittest discover -s demo_showcase/tests -p "test_*.py" -v` and verify it fails because production modules do not exist.
- [ ] Commit the red tests with message `Test three detector demo interfaces`.

### Task 2: Implement the player and video builder

**Files:**
- Create: `demo_showcase/player.py`
- Create: `demo_showcase/build_videos.py`
- Create: `demo_showcase/assets/plate_result.jpg`
- Create: `demo_showcase/assets/traffic_light_result.jpg`
- Create: `demo_showcase/assets/fire_smoke_result.jpg`

- [ ] Copy only selected visual evidence into the new tracked assets directory; do not stage or modify `traffic_light/`.
- [ ] Implement `player.py` with `resolve_video`, `build_parser`, `validate_video`, a looping `play` function, and `Q`/`Esc` exit handling.
- [ ] Implement `build_videos.py` with three declarative module definitions, `fit_frame`, label/banner composition, subtle zoom animation, per-module MP4 generation and a horizontal 3-panel combined MP4.
- [ ] Use OpenCV `VideoWriter` with `mp4v`, 12 FPS, 10 seconds, and check `isOpened()` plus output readability.
- [ ] Run the demo tests and verify they pass.
- [ ] Commit code and source frames with message `Add three detector demo player`.

### Task 3: Generate compact answer-defense videos

**Files:**
- Create: `demo_showcase/videos/license_plate_demo.mp4`
- Create: `demo_showcase/videos/traffic_light_demo.mp4`
- Create: `demo_showcase/videos/fire_smoke_demo.mp4`
- Create: `demo_showcase/videos/三项识别答辩演示.mp4`

- [ ] Run `python demo_showcase/build_videos.py`.
- [ ] Verify each MP4 opens, has at least 100 frames, and reports nonzero dimensions through OpenCV.
- [ ] Confirm total video size remains suitable for local demo and all MP4 files are stored by Git LFS.
- [ ] Commit generated media with message `Add compact three detector demo videos`.

### Task 4: Add the one-click launcher and documentation

**Files:**
- Create: `一键启动三项识别演示.bat`
- Create: `demo_showcase/README.md`

- [ ] Add a BAT self-check mode `--check` that validates Python, OpenCV, player and all three videos without opening GUI windows.
- [ ] Default BAT behavior uses three `start` commands, unique titles and positions to launch all windows concurrently.
- [ ] Print the absolute combined-video fallback path when checks fail and in the normal startup summary.
- [ ] Document the 30-second operating sequence for the defense and the `Q`/`Esc` controls.
- [ ] Run `cmd /c "一键启动三项识别演示.bat --check"` and verify exit code 0.
- [ ] Commit with message `Add one-click three detector demo`.

### Task 5: Full verification and merge

**Files:**
- Modify only if verification finds a proven issue.

- [ ] Run `python -m unittest discover -s demo_showcase/tests -p "test_*.py" -v`.
- [ ] Run the existing seven fire/smoke tests and Python compilation.
- [ ] Run BAT `--check`, inspect first frames and verify the combined fallback video.
- [ ] Run a timed GUI smoke test that starts three players, confirms three Python processes stay alive, then closes only those test processes.
- [ ] Confirm `git status --short` contains only the four protected pre-existing untracked paths.
- [ ] Merge `codex/fire-smoke-migration` into `main` with `--no-ff`, rerun the critical checks on `main`, and do not push.
