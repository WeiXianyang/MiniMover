# MiniMover 导航改动：导出与合并建议（仅仓库内）

> 容器 / `yahboomcar_ws` **不在本仓库导出范围**。前端同学只吃 `MiniMover`。  
> 车上 ROS/容器改动（`nav_stack.sh`、`laser_bringup` 等）留在小车，另轨维护。

---

## 1. 建议拉进 GitHub 的内容（相对 MiniMover 根）

### 整目录新增/替换（以小车版为准）

```
navigation/                 # 导航 API + 巡逻网页 + 启停管理
scripts/start_nav_api.sh    # 导航模式起 :5000（默认关相机）
scripts/stop_for_nav.sh     # 导航准备（默认不停相机）
.doc/导航巡逻API接口文档.md
.doc/MiniMover导航合并建议.md   # 本文件
```

### 需合并的单文件（不要整文件覆盖丢掉别处更新）

```
api_server.py
```

### 可不进「导航 PR」但仍建议保持可运行的依赖

- 现有 `sensors/`、`audio/`、火灾检测等——旧仓库有就保留，**本次导航不必删**。

---

## 2. 打包示例（小车上）

```bash
cd ~/MiniMover
tar czf ~/MiniMover-nav-patch.tar.gz \
  navigation \
  scripts/start_nav_api.sh \
  scripts/stop_for_nav.sh \
  .doc/导航巡逻API接口文档.md \
  .doc/MiniMover导航合并建议.md \
  api_server.py
```

或直接在本仓库开分支提交上述路径。

---

## 3. 和「外面已有更新」的合并策略

假设：GitHub / 本机仓库里 `api_server.py`、业务代码已经比小车旧底更新；小车多了导航。

**原则：导航用小车的 `navigation/` + 两个脚本；`api_server.py` 做补丁合并，别用小车整文件盖掉外面的新功能。**

### 步骤

1. 备份本机当前分支。  
2. 把小车的 `navigation/` **整目录放进仓库**（若本机已有旧 `navigation/`，以小车版功能为准做 diff；保留本机 `navigation/data/routes/` 里已有路线若需要）。  
3. 放入/更新 `scripts/start_nav_api.sh`、`scripts/stop_for_nav.sh`。  
4. **合并 `api_server.py`（关键补丁清单）**：

| 补丁 | 做什么 |
|------|--------|
| import | `from navigation import nav_bp, register_legacy_routes, register_patrol_page` |
| 注册 | `app.register_blueprint(nav_bp, url_prefix='/api/nav')` → `register_legacy_routes(app)` → `register_patrol_page(app)` |
| 去冲突 | 若本机仍有内联 `@app.route('/api/map')` / `map_image` / `navigate`，删掉或改接蓝图（`register_legacy_routes` 已提供兼容路径） |
| 可选 | `MINIMOVER_DISABLE_CAMERA` + `/video_feed` 无相机占位（导航联调不抢相机） |
| 首页 | 链接 `/nav/patrol`（地图巡逻）、可保留 `/nav` 单点导航 |
| 保留 | 火灾检测、音频、传感器、`/api/move`、外面同学已加的新接口/UI **全部保留** |

5. 文档：`.doc/导航巡逻API接口文档.md` 给前端对接用。  
6. 自测（有车时）：`bash scripts/start_nav_api.sh` → 打开 `/nav/patrol`。

---

## 4. `navigation/` 给前端看什么

| 路径 | 前端关心点 |
|------|------------|
| `routes.py` | REST：`/api/nav/*` |
| `patrol_page.py` | 交互参考页 `/nav/patrol`（按钮顺序、何时调用 API） |
| `.doc/导航巡逻API接口文档.md` | 正式对接说明 |
| `stack_manager.py` / `ros_bridge.py` | 后端细节；前端只需知道 start 秒回、轮询 status 到 ready |

### 前端推荐调用顺序

1. `POST /api/nav/stack/start`（`wait_ready: false`）→ 立刻提示「已开始」  
2. 轮询 `GET /api/nav/stack/status` 直到 `patrol_ready` / `stack_ready`  
3. `GET /api/nav/map` + `GET /api/nav/map/image`  
4. `POST /api/nav/initial_pose` → `POST /api/nav/patrol/route` → `POST /api/nav/patrol/start`  
5. 退出：`POST /api/nav/patrol/stop` → `POST /api/nav/stack/stop`

---

## 5. 不要删 / 不要做的事

- 不要用小车 `api_server.py` **整文件覆盖** GitHub 上已更新的版本。  
- 不要把 `code/yahboomcar_ws`、docker 配置塞进这个给前端的 PR（车侧环境另管）。  
- 不要删火灾、音频、遥控、外面新加的业务路由。  
- 不要删 `navigation/data/routes/` 里已有路线（若有）。  

---

## 6. 给负责合并的 Cursor 的一句话

> 以当前 GitHub/本机 `api_server.py` 为底，合入小车导航三件套：`navigation/` 整目录 + 两个 scripts + api_server 导航注册补丁；业务逻辑一律保留；容器相关不进仓库。
