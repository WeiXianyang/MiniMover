# Repository Guidelines

## Project Structure & Module Organization

This directory is a course-material package for iCar smart-car usage and chassis firmware flashing. Keep the top-level `智能小车使用手册.pdf` as the primary student-facing manual. Store installation and flashing utilities under `工具/`, including `AT32IDE_V1.0.10_Setup.exe`, `sscom5.13.1.exe`, Artery DFU driver installer, and Artery ISP Programmer packages. Store firmware images only under `底盘固件包/`: `iCar.bin` for normal ROS features and `follow-line.bin` for line-following or IoT data-collection demos. Keep short operational notes in `底盘固件包/说明.txt`.

## Build, Test, and Development Commands

There is no source build system in this package. Validate materials with file and tool checks:

- `Get-ChildItem -Recurse`: review the full package contents.
- `Get-FileHash 底盘固件包\*.bin`: record firmware checksums before distribution.
- `Get-FileHash 工具\**\*.exe`: verify tool installers have not changed unexpectedly.
- Open `智能小车使用手册.pdf`: confirm the manual renders and matches the distributed firmware/tools.

## Coding Style & Naming Conventions

Use stable, descriptive filenames. Preserve vendor names and versions for tools, such as `AT32IDE_V1.0.10_Setup.exe` and `Artery_ISP_Programmer_V2.0.13.zip`. Firmware filenames should stay lowercase or camel-style and end in `.bin`; do not rename `iCar.bin` or `follow-line.bin` unless the manual and `说明.txt` are updated together. Keep Chinese instructional notes concise and numbered when describing flashing choices.

## Testing Guidelines

For every firmware update, verify flashing with Artery ISP Programmer and confirm the matching behavior on hardware. Test `iCar.bin` with normal ROS functions such as radar obstacle avoidance, mapping, navigation, and app control. Test `follow-line.bin` with line-following and IoT data-collection demonstrations. Record firmware hash values, tool version, board model, and test date in release notes.

## Commit & Pull Request Guidelines

This directory is not currently a git repository, so no commit history convention is available. If versioned later, use concise imperative messages such as `Update iCar chassis firmware` or `Refresh Artery ISP tool package`. Pull requests should list changed files, reason for update, firmware hashes, tested hardware, and screenshots or photos for UI/tooling changes.

## Security & Configuration Tips

Do not add personal serial-port logs, Wi-Fi credentials, license keys, or unpublished vendor packages. Treat `.exe`, `.zip`, and `.bin` files as release artifacts: replace them intentionally, document their source, and keep checksums for auditability.
