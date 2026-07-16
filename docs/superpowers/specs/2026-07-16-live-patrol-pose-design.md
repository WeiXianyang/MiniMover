# 实时巡逻位姿显示设计

**日期：** 2026-07-16  
**范围：** 在地图巡逻控制台显示小车的实时位置、朝向、定位来源与新鲜度；不改变导航、避障或底盘控制逻辑。

## 背景与调查结论

巡逻页面目前只绘制网页手动设置的起点和路线点。它既未请求实时位姿 API，也没有机器人 marker。Flask 的 `/api/nav/*` 也没有位姿接口。

Jetson 的导航容器中，`base_node_X3` 发布 `/odom_raw`；导航地图的正确坐标系应优先使用 `map`。`/amcl_pose` 或 TF `map -> base_footprint` 才能可靠地叠加到静态地图。轮速里程计不能直接作为地图位置，因为其坐标在 `odom` 中并会漂移。

## 方案比较

1. **每次网页请求执行 `ros2 topic echo`**：实现快，但 Foxy 不支持当前代码中使用的 `--once`，且频繁启动 Docker/ROS CLI 容易阻塞 Flask。**不采用。**
2. **页面直接连接 ROS**：浏览器无法安全、稳定地直连 DDS，且会把 ROS 网络暴露给客户端。**不采用。**
3. **由已运行的 `route_patrol` 缓存并提供 ROS 服务，Flask 将服务转换为 HTTP JSON**：数据在 ROS 侧持续可用，HTTP 层只做短服务调用；可返回明确的有效性与降级状态。**采用。**

## 数据契约

新增 `yahboomcar_patrol_interfaces/srv/GetRobotPose.srv`：

```srv
---
bool valid
geometry_msgs/PoseStamped pose
string source
string message
```

服务名为 `/patrol/get_robot_pose`。返回规则：

- 首选 `map -> base_footprint` TF，`source="tf"`；
- TF 暂不可用时，使用未过期的 `/amcl_pose`，`source="amcl_pose"`；
- 两者都无有效数据时，`valid=false`，保留明确错误信息；绝不把 `odom` 当作 `map` 位姿返回。

`route_patrol` 将维护 TF buffer 和 `/amcl_pose` 最新缓存。新增参数 `pose_max_age`，默认 3 秒。

## HTTP API

新增只读接口：

```text
GET /api/nav/pose
```

成功响应 `data` 包含：

```json
{
  "valid": true,
  "x": 1.25,
  "y": -0.8,
  "yaw": 0.52,
  "frame_id": "map",
  "source": "tf",
  "stamp": {"sec": 0, "nanosec": 0},
  "message": "ok"
}
```

`valid=false` 仍返回 HTTP 200，使页面能显示“定位等待中”而非把暂时无定位误报为 API 故障。Flask 进程会做短 TTL 缓存，避免同一轮页面轮询重复调用 Docker/ROS CLI。

## 页面行为

巡逻页在地图容器内新增机器人箭头和“实时位姿”面板：

- 每秒请求 `/api/nav/pose`；
- 有效的 `map` 位姿按已有 `map_to_pixel` 逆变换显示为蓝色箭头；
- yaw 转为屏幕旋转角（屏幕 Y 轴向下）后显示当前朝向；
- 文本显示 `(x, y)`、yaw 度数、来源、更新时间；
- 位姿无效或不在 `map` 坐标系时隐藏箭头并显示定位等待/降级信息；
- 起点与路线仍按原逻辑绘制，不改变巡逻控制操作。

## 测试与验收

1. `ros_bridge` 单元测试覆盖服务输出中有效 TF 位姿、无效定位和 yaw 四元数解析。
2. Flask 测试覆盖 `GET /api/nav/pose` 的稳定 JSON 形状和 HTTP 200 降级响应。
3. 页面测试验证存在机器人 marker、位姿轮询和无效状态渲染路径。
4. ROS 工作空间构建 `yahboomcar_patrol_interfaces` 与 `yahboomcar_nav`。
5. Jetson 上启动导航栈后，在机器人运动时确认 `/api/nav/pose` 返回 `valid=true`、`frame_id="map"`，且网页箭头与 RViz 中机器人位置/朝向一致。

## 非目标

- 不修改 DWB、代价地图、避障参数或底盘控制。
- 不用 `/odom_raw` 伪造地图坐标。
- 不向外暴露 ROS DDS 或直接把控制权限交给网页。
