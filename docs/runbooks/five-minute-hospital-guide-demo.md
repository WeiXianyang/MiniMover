# 五分钟医院导诊小车演示 Runbook

> **安全放行规则：** `voice_assistant/data/hospital_guide_template.json` 中所有导航点位当前保持 `enabled: false`。在完成真实坐标采集、双人复核（两名操作员）和连续三次试跑并填写本页放行记录之前，**不得**启用 `internal_medicine`，更不得为其它科室启用导航。

## 适用范围与不可替代的安全措施

- 本流程只允许演示内科（`internal_medicine`）导航；其它科室始终保持禁用。
- 人脸识别只用于欢迎显示名。相机、识别或低置信度失败必须降级为“访客”，不得阻塞导诊。
- 不导出、展示或记录照片、候选项、置信度、语音原文、病历、电话、邮箱、密码或其它身份资料。
- `ACTIVE`、HTTP 200、目标已提交和 TTS 播完都不代表到达。仅当 `status.arrived=true` 时才可播报到达：该字段要求 Nav2 `SUCCEEDED` 且有效 `map` 位姿距终点不超过 `0.15 m`。
- 硬件停止路径和现场安全操作员优先于任何软件命令。普通 move API 不可替代 Nav2 取消。

## 演示前检查

- 清场、指定安全操作员和硬件停止路径。
- 检查 `/api/nav/stack/status` 与 `/api/nav/pose`；`valid` 必须为 `true`，`frame_id` 必须为 `map`。
- 预注册演示者；不导出照片、候选项或置信度。
- 将车辆放到已批准的固定起点，确认电量、急停、激光雷达、相机、Nav2 和定位均可用。
- 确认显示控制台不会显示人脸信息、语音原文或取消/移动控制按钮。

## 内科点位标定与启用前放行

1. 启动实际使用的 Nav2 地图环境，确认：
   ```bash
   ros2 action list | grep navigate_to_pose
   ros2 service list | grep patrol/get_robot_pose
   curl -fsS http://127.0.0.1:5000/api/nav/pose
   ```
2. 在固定起点设置初始位姿；在清场条件下手动把车移至安全的内科候诊区终点。
3. 从 pose API 记录有限十进制的 `x`、`y`、`yaw`，由第二名操作员独立复核记录与实际位置。
4. 仅将 `internal_medicine.navigation` 改为真实 `x`、`y`、`theta` 和 `enabled: true`。禁止写入 `(0.0, 0.0)`、尖括号占位符或推测坐标；其它科室继续 `enabled: false`。
5. 从同一固定起点连续实走三次。每次都记录 action 最终状态、`pose.valid`、`pose.frame_id`、终点距离、`0.15 m` 判定和人工确认停车结果。任何失败立即重新禁用内科；修复后从第一次重新计数。

### 三次试跑记录

| 试跑 | 日期/时间 | 操作员 | Nav2 最终状态 | pose valid / frame_id | 距离 (m) | arrived | 人工确认停车 | 结果 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |  |

## 启动

1. 在 PC 上运行 `hostname -I` 获取 ASR 主机 IPv4；将实际 IPv4 作为第一个参数运行：
   ```bash
   bash scripts/start_hospital_guide_demo.sh 192.168.1.10 8765
   ```
2. 打开 `/hospital-guide`、`/nav/patrol`、`/api/hospital-guide/demo/status`。
3. 确认控制台显示匿名阶段、欢迎显示名或访客、Nav2 action 状态、目标、`map` 位姿、距离、容差和恢复原因；不显示人脸或语音详情。

## 五分钟脚本

1. **00:00–00:30**：`POST /api/hospital-guide/demo/start`，等待个人或访客欢迎。
2. **00:30–01:30**：说“我要去内科”。
3. **01:30–02:00**：说“好的，带我去”。
4. **02:00–04:30**：安全操作员随车，`ACTIVE` 不得称为到达。
5. **04:30–05:00**：仅 `status.arrived=true` 时播报到达；否则报告真实原因并安全结束。

## 恢复

- 相机或人脸失败：访客导诊；不阻塞。
- ASR/TTS 失败：结束本轮，重新 start；不手工伪造 ack。
- Nav2 或定位失败：报告失败，安全停止，重新标定。
- 取消仅在 `MINIMOVER_DEMO_CANCEL_ENABLED=1` 且实车验证后使用；move API 不可替代。
- 任何急停、障碍物或人工安全判断中断：以硬件停止路径处置，待现场安全操作员确认后才可重新开始。

## 放行记录

- 内科坐标（x / y / theta）：
- 坐标采集人：
- 复核人 1：
- 复核人 2：
- 三次试跑记录已附：是 / 否
- 软件 commit：
- 演示日期：
- 现场安全操作员：
- 最终放行人：

只有所有字段完整且三次试跑均满足双条件到达判定时，方可启用内科导航进行演示。
