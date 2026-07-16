# 五分钟医院导诊演示：只读现场预检脚本设计

## 状态

**待评审。** 本文定义一个仅用于现场接入确认的预检脚本；在评审和实现完成前，不改变现有小车、导航或导诊运行行为。

## 背景与目标

现有 runbook 已列出 Nav2 action、`/api/nav/pose` 和控制台的人工检查命令。实际现场容易遗漏 ROS 域、API 地址或定位状态，且不能用“页面能打开”替代导航放行证据。

新增 `scripts/check_hospital_guide_preflight.sh`，将这些检查收敛为一次**只读**预检。它的目标是为安全操作员提供简洁、可保存的“通过 / 未通过 / 无法检查”报告；它不取代内科坐标双人复核和三次实车试跑。

## 非目标与硬性安全边界

脚本必须：

- 不调用任何 `POST`、`PUT`、`PATCH` 或 `DELETE` HTTP 请求；
- 不调用导航或底盘的 start、stop、cancel、move、route 或 initial-pose 接口；
- 不执行 `nav_stack.sh`、`start_services.sh`、Docker、`ros2 launch`、`ros2 run`、`ros2 service call` 或任何会使小车移动的命令；
- 不改写环境文件、地图、坐标、JSON 配置或 ROS 参数；
- 不输出 API 的完整 JSON、人脸信息、ASR 文本、姓名、电话、邮箱或其它可能的身份信息；
- 不把“HTTP 可达”或“action 存在”报告为“已放行”。

`internal_medicine.navigation.enabled` 继续由现场三次试跑证据控制，预检脚本无权修改它。

## 命令行契约

```bash
bash scripts/check_hospital_guide_preflight.sh \
  --api-base http://127.0.0.1:5000 \
  --ros-domain 30
```

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--api-base URL` | 是 | 车端 Flask API 根地址。仅接受 `http://` 或 `https://` URL；脚本将其规范化后用于固定的 GET 路径。 |
| `--ros-domain N` | 否 | 非负整数。提供时，仅对子进程 `ros2` 命令设置 `ROS_DOMAIN_ID=N`，不改写调用者环境。 |
| `--timeout-seconds N` | 否 | 每个 HTTP GET 的连接/总超时，默认保守的 2 秒；必须是有限正整数。 |
| `--help` | 否 | 输出用法并以 0 退出。 |

未知参数、重复参数、非法 URL 或非法数值必须在执行任何网络请求前以用法错误退出。

## 检查流程

### 1. 本地依赖与参数

脚本检查 `curl`；若需要解析稳定 JSON 字段，则只使用已存在的 `python3` 标准库。缺少依赖时报告为 `UNAVAILABLE`，不尝试安装软件。

### 2. 固定 HTTP GET 检查

仅请求以下固定路径：

- `GET /api/nav/stack/status`
- `GET /api/nav/pose`
- `GET /api/hospital-guide/demo/status`

每项输出 HTTP 可达性和最小匿名状态。`/api/nav/pose` 仅提取并显示 `valid` 与 `frame_id`；不显示完整响应，也不从单个 pose 响应推断到终点距离。只有 `valid=true` 且 `frame_id=map` 才标为定位前置条件通过。

HTTP 连接失败、超时、非 2xx、无效 JSON 或字段缺失均为 `FAIL` 或 `UNAVAILABLE`，但脚本继续执行其它只读检查，最后汇总所有问题。

### 3. ROS 2 发现检查

当 `ros2` 可用时，脚本读取而不控制 ROS 图：

- 列出节点，仅报告数量；
- 列出 action 类型，仅判断是否存在 `navigate_to_pose`；
- 列出 topic 类型，仅判断 `/map`、`/amcl_pose`、`/tf`、`/odom`、`/scan` 是否可见。

脚本不得显式执行 `ros2 daemon start`、`ros2 daemon stop` 或任何控制类 ROS CLI 命令，也不得启动导航栈。若 ROS CLI 本身的发现机制创建本地辅助进程，脚本不将其视为车端服务就绪；若 ROS CLI 不可用、DDS 不可达或查询失败，结果为 `UNAVAILABLE`。

### 4. 报告与退出码

报告采用固定、可读的行格式，例如：

```text
[PASS] api.nav_pose: valid=true frame_id=map
[PASS] ros.navigate_to_pose: action visible
[PENDING] release_gate: real-coordinate review and three test runs are still required
```

脚本永远明确输出 `release_gate`：除非运行者人工提供并核对 runbook 中的真实证据，否则结论保持 `PENDING`。这样可防止把自动检查误读为实车放行。

退出码：

- `0`：所有自动、只读前置项可检查且通过；`release_gate` 仍会显示为 `PENDING`，且不会代表实车已放行。
- `1`：一个或多个自动前置项失败或不可用。
- `2`：命令行参数或本地临时目录初始化错误。缺少 `curl`、`python3` 或 `ros2` 统一按自动检查不可用处理，返回 `1`。

## 测试策略

在不接触真实网络和 ROS 图的前提下，为脚本添加独立测试夹具：

1. 用临时 PATH 下的 `curl` stub 记录方法和 URL，验证仅调用 GET 以及固定的三个端点；
2. 用 `ros2` stub 验证仅执行 list 查询，不出现 launch/run/service/call/start/stop；
3. 覆盖参数校验、HTTP 超时/非 2xx、无效 JSON、`pose.valid=false`、frame 不是 `map`、缺少 `navigate_to_pose` 和完全通过的报告；
4. 断言脚本输出不回显 stub 返回的身份或语音敏感字段；
5. 运行现有医院导诊、导航配置和启动脚本测试，确认本次新增工具不改变运行时演示路径。

## 验收标准

- 在没有运行 API 或 ROS 的开发机上，脚本只报告不可用/失败，不启动导航、底盘或 API 服务，也不改写任何文件；
- 在 stub 的健康场景中，报告准确显示 API、地图位姿和 Nav2 action 可见性；
- 在任何场景中，脚本不发送非 GET HTTP 方法、不发 ROS 控制调用、不启用内科导航；
- 输出中不包含完整 HTTP body 或身份、语音内容；
- runbook 明确注明：预检通过后仍需真实坐标、两名操作员复核和固定起点连续三次实车试跑。

## 备选方案

只扩充 runbook 的人工命令不需要脚本维护，但不能统一超时、ROS 域传递、最小隐私输出和失败汇总。选择独立脚本，是为了降低现场漏检风险，同时保持默认只读和不可放行的安全边界。

## 评审请求

请确认以下设计决定：

1. 预检工具只读，且不提供任何启动、停止、取消或运动选项；
2. 自动检查通过仍明确不等于实车放行；
3. 默认 API 超时为 2 秒，ROS 域仅对子进程生效；
4. 输出只含匿名状态与导航安全字段，不输出完整响应体。
