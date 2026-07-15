# 地图巡逻 API 接口文档（客户端对接）

> 服务地址：`http://<小车IP>:5000`  
> 模块代码目录：`MiniMover/navigation/`  
> Web 参考页：`http://<小车IP>:5000/nav/patrol`（**建议客户端 UI 参考此页面**）

---

## 1. 概述

本模块提供「地图加载 → 设置起点 → 画巡逻路线 → 自动巡检 → 退出释放资源」的完整 HTTP API。

**客户端无需 SSH**，也**无需手动进容器执行 p1**。  
进入巡逻功能前调用 `POST /api/nav/stack/start` 即可自动启动导航栈（等同容器内 `p1` 命令）。

### 1.1 代码目录结构

```
MiniMover/
├── api_server.py                 # Flask 主入口，注册 navigation 蓝图
└── navigation/                   # ★ 所有导航/巡逻接口集中在此目录
    ├── __init__.py
    ├── config.py                 # 容器名 ded7、地图路径、ROS_DOMAIN_ID
    ├── map_utils.py              # 地图读取、坐标转换
    ├── ros_bridge.py             # docker exec 调用 ROS 服务
    ├── stack_manager.py          # 一键启动/停止 p1 导航栈
    ├── routes.py                 # Flask 路由（/api/nav/*）
    ├── patrol_page.py            # Web 测试页 HTML
    └── data/routes/              # 保存的巡逻路线 JSON
```

容器内辅助脚本（挂载自宿主机）：

```
code/yahboomcar_ws/scripts/nav_stack.sh   # p1 启动/停止脚本
```

### 1.2 统一响应格式

成功：

```json
{"code": 0, "msg": "ok", "data": { ... }}
```

失败：

```json
{"code": -1, "msg": "错误描述"}
```

---

## 2. App 推荐使用流程

```
┌─────────────────────────────────────────────────────────┐
│  用户打开「地图巡逻」页面                                   │
└────────────────────────┬────────────────────────────────┘
                         ▼
              POST /api/nav/stack/start
              （自动启动 ded7 + p1，等待就绪）
                         ▼
              GET  /api/nav/map
              GET  /api/nav/map/image
              （加载地图显示）
                         ▼
              用户在地图上点击设起点、路径点
              （客户端用 coord 公式或 API 换算坐标）
                         ▼
              POST /api/nav/initial_pose
              POST /api/nav/patrol/route
              POST /api/nav/patrol/start
                         ▼
              GET  /api/nav/patrol/status（轮询）
                         ▼
              用户退出页面
              POST /api/nav/patrol/stop（如在巡逻中）
              POST /api/nav/stack/stop（释放资源）
```

> **重要**：巡逻模式与 FireGuard 手动遥控（`/api/move`）**互斥**，共用底盘串口。进入巡逻前请勿使用遥控。

---

## 3. 导航栈管理（无需 SSH）

### 3.1 查询状态

```
GET /api/nav/stack/status
```

**响应 data 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| container | string | 容器名，默认 `ded7` |
| container_running | bool | ded7 是否在运行 |
| patrol_ready | bool | 巡逻服务是否就绪（p1 是否在跑） |
| stack_ready | bool | 同 patrol_ready |
| ros_domain_id | string | ROS 域 ID，默认 `30` |
| hint | string | 未就绪时的提示 |

**示例：**

```bash
curl http://192.168.137.23:5000/api/nav/stack/status
```

---

### 3.2 一键启动导航栈（等同 p1）

```
POST /api/nav/stack/start
Content-Type: application/json
```

**请求体（均可选）：**

```json
{
  "wait_ready": true,
  "timeout": 45
}
```

| 字段 | 默认 | 说明 |
|------|------|------|
| wait_ready | true | 是否阻塞等待巡逻服务就绪 |
| timeout | 30 | 等待就绪最长时间（秒） |

**行为：**
1. 若 ded7 未运行，自动 `docker start ded7`
2. 在容器内后台执行 `ros2 launch yahboomcar_nav patrol_bringup_launch.py`
3. 轮询直到 `/patrol/set_route` 服务出现（约 10~15 秒）

**响应 data 示例：**

```json
{
  "success": true,
  "message": "导航栈已就绪，可以设置路线并巡逻",
  "patrol_ready": true,
  "pid": 12345,
  "log": "/tmp/p1_stack.log"
}
```

**App 调用时机：** 用户进入「地图巡逻」页面前或页面 onLoad 时。

---

### 3.3 一键关闭导航栈（退出时调用）

```
POST /api/nav/stack/stop
```

**行为：**
1. 若正在巡逻，先调用 `/patrol/stop`
2. 停止 p1 相关进程（Nav2、雷达、底盘驱动、巡逻节点等）
3. 释放 `/dev/myserial` 和雷达资源

**App 调用时机：** 用户离开巡逻页面、或 App 切换到其他需要遥控的功能前。

---

## 4. 地图与坐标

### 4.1 获取地图元信息

```
GET /api/nav/map
GET /api/nav/map?map=loudao
```

**响应 data：**

```json
{
  "map": "loudao",
  "width": 800,
  "height": 600,
  "resolution": 0.05,
  "origin": [-10.0, -21.2, 0.0]
}
```

- `resolution`：米/像素
- `origin`：地图左下角在 ROS map 坐标系中的位置

---

### 4.2 获取地图图片

```
GET /api/nav/map/image
```

返回 JPEG 图片，可直接作为 `<Image>` 组件背景。

> 客户端可将地图图片打包进 App，也可每次从服务器拉取。  
> 当前默认地图：`loudao`（与 p1 导航栈一致）。

---

### 4.3 屏幕点击 → ROS 坐标（与 RViz 一致）

**方式 A：客户端自行计算（推荐，减少请求）**

```javascript
// mapInfo 来自 GET /api/nav/map
// clickX, clickY 为相对地图图片显示区域的像素坐标
// displayWidth, displayHeight 为图片控件显示宽高
// mapInfo.width/height 为地图原始像素尺寸

const pixelX = clickX * mapInfo.width / displayWidth;
const pixelY = clickY * mapInfo.height / displayHeight;

const mapX = pixelX * mapInfo.resolution + mapInfo.origin[0];
const mapY = (mapInfo.height - pixelY) * mapInfo.resolution + mapInfo.origin[1];
// mapX, mapY 即为 ROS map 坐标，与 RViz Publish Point 一致
```

**方式 B：调用后端换算**

```
POST /api/nav/coord/pixel_to_map
Content-Type: application/json

{
  "screen_x": 200,
  "screen_y": 150,
  "display_width": 400,
  "display_height": 300
}
```

**响应：**

```json
{
  "code": 0,
  "data": {
    "x": 3.012,
    "y": -0.071,
    "pixel_x": 260.0,
    "pixel_y": 424.0
  }
}
```

---

## 5. 起点与巡逻路线

### 5.1 设置起点（小车在地图上的位置）

```
POST /api/nav/initial_pose
Content-Type: application/json

{"x": 0.0, "y": 0.0, "yaw": 0.0}
```

| 字段 | 说明 |
|------|------|
| x, y | map 坐标系位置（米） |
| yaw | 车头朝向（弧度），0 = 朝 X 正方向 |

> 开始巡逻前**必须**设置正确起点，否则 Nav2 定位会偏。

---

### 5.2 设置巡逻路线

```
POST /api/nav/patrol/route
Content-Type: application/json

{
  "points": [
    [3.0, -0.0712],
    [5.44, -0.075],
    [5.61, -5.45],
    [0.0, 0.0]
  ]
}
```

也支持对象格式：

```json
{"points": [{"x": 3.0, "y": -0.0712}, {"x": 5.44, "y": -0.075}]}
```

- 至少 **2 个点**
- 整批**替换**当前路线（非追加）
- 巡逻进行中不可修改，需先 `patrol/stop`

---

### 5.3 读取当前路线

```
GET /api/nav/patrol/route
```

**响应 data：**

```json
{
  "success": true,
  "point_count": 4,
  "patrol_active": false,
  "loop": true,
  "points": [{"x": 3.0, "y": -0.0712}, ...]
}
```

---

### 5.4 开始巡逻

```
POST /api/nav/patrol/start
```

前提：导航栈已就绪 + 已设置至少 2 个路径点。

---

### 5.5 停止巡逻（不关闭导航栈）

```
POST /api/nav/patrol/stop
```

仅停止当前巡逻任务，导航栈保持运行，可重新设置路线后再启动。

---

### 5.6 清空路线

```
POST /api/nav/patrol/clear
```

---

### 5.7 查询巡逻状态（轮询）

```
GET /api/nav/patrol/status
```

**响应 data 示例：**

```json
{
  "status": "navigating to waypoint 2 / 8",
  "patrol_active": true,
  "point_count": 4,
  "loop": true
}
```

建议每 2~3 秒轮询一次。

---

### 5.8 设置是否循环巡逻

```
POST /api/nav/patrol/loop
Content-Type: application/json

{"loop": true}
```

---

## 6. 路线保存与加载

### 6.1 列出已保存路线

```
GET /api/nav/patrol/routes
```

### 6.2 保存路线

```
POST /api/nav/patrol/routes/<名称>
Content-Type: application/json

{
  "points": [[3.0, -0.07], [5.44, -0.075]],
  "map": "loudao",
  "initial_pose": {"x": 0, "y": 0, "yaw": 0},
  "loop": true
}
```

不传 `points` 时保存当前 ROS 中的路线。

### 6.3 加载路线到 ROS

```
POST /api/nav/patrol/routes/<名称>/load
Content-Type: application/json

{"apply_initial_pose": true}
```

---

## 7. 单点导航（可选）

```
POST /api/nav/navigate
Content-Type: application/json

{"x": 2.0, "y": 1.0, "theta": 0.0}
```

导航到单个目标点（非巡逻模式）。

---

## 8. 兼容旧接口

以下旧路径仍可用，内部转发到 `/api/nav/*`：

| 旧路径 | 新路径 |
|--------|--------|
| GET /api/map | GET /api/nav/map |
| GET /api/map_image | GET /api/nav/map/image |
| POST /api/navigate | POST /api/nav/navigate |

---

## 9. Web 参考页说明

访问：**`http://<小车IP>:5000/nav/patrol`**

该页面是「地图巡逻控制台」测试页，标题和说明已写清楚用途：

- **是什么**：地图巡逻功能测试与演示
- **给谁用**：开发测试 + **客户端 UI/交互参考**
- **做什么**：启动导航栈 → 设起点 → 画路径 → 巡逻 → 关闭导航栈

客户端开发时可对照该页面的：
- 按钮布局与操作流程
- 地图点击设点交互
- API 调用顺序
- 状态提示文案

首页 `http://<小车IP>:5000/` 也有 **「巡逻测试」** 入口链接。

---

## 10. 完整 curl 测试示例

```bash
IP=192.168.137.23

# 1. 启动导航栈
curl -X POST http://$IP:5000/api/nav/stack/start \
  -H "Content-Type: application/json" \
  -d '{"wait_ready":true,"timeout":45}'

# 2. 确认就绪
curl http://$IP:5000/api/nav/stack/status

# 3. 设起点
curl -X POST http://$IP:5000/api/nav/initial_pose \
  -H "Content-Type: application/json" \
  -d '{"x":0,"y":0,"yaw":0}'

# 4. 设路线
curl -X POST http://$IP:5000/api/nav/patrol/route \
  -H "Content-Type: application/json" \
  -d '{"points":[[3,-0.07],[5.44,-0.08],[5.61,-5.45],[0,0]]}'

# 5. 开始巡逻
curl -X POST http://$IP:5000/api/nav/patrol/start

# 6. 查状态
curl http://$IP:5000/api/nav/patrol/status

# 7. 停止并退出
curl -X POST http://$IP:5000/api/nav/patrol/stop
curl -X POST http://$IP:5000/api/nav/stack/stop
```

---

## 11. 常见问题

| 问题 | 处理 |
|------|------|
| patrol_ready=false | 调用 `POST /api/nav/stack/start` |
| service unavailable | 导航栈未就绪或 ROS_DOMAIN_ID 不一致（默认 30） |
| 小车不动 | 检查起点是否设对；路径点是否在白色可通行区 |
| 与遥控冲突 | 巡逻时不要调用 `/api/move` |
| ded7 启动失败 | 先 `bash ~/MiniMover/scripts/stop_for_nav.sh` 释放摄像头 |

---

## 12. 环境前提

1. 宿主机已安装 Docker，容器名为 `ded7`
2. 已编译 `yahboomcar_patrol_interfaces` 和 `yahboomcar_nav`
3. API 服务运行：`bash ~/MiniMover/scripts/start_nav_api.sh`
4. 巡逻模式建议先停止 FireGuard 全套服务，避免抢串口/摄像头
