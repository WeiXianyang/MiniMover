1# FireGuard 工业巡检 APP 页面改造说明

本文档记录本次将原「智慧小车」遥控应用按 `figma-car-app-pages` 原型改造为
「FireGuard 工业巡检 APP」的全部文件改动与内容。

## 一、改造目标

依据页面原型（竖屏手机布局、深蓝主题、7 项底部标签栏），把原横屏平板遥控应用
重构为 FireGuard 巡检控制台。三条关键决策：

1. 屏幕方向：横屏 → **竖屏**
2. 数据页面（地图/告警/配送/报告）：先做页面，数据用原型静态值占位，后端后续接入
3. 原有真实控制能力（四轮调速、按钮/摇杆驾驶、视频、拍摄录制、自动循迹）：**折叠进「手动接管」页**

## 二、新增文件

### 设计系统 `entry/src/main/ets/fireguard/`

| 文件 | 内容 |
| --- | --- |
| `Theme.ets` | 设计令牌（`FG` 命名空间）：颜色、字号、圆角，取自原型 `styles.css` 的 `:root` 变量。深蓝底 + 橙/青/绿/红强调色 |
| `Widgets.ets` | 通用组件：`FgPill`（状态徽标）、`FgPageHead`（页头）、`FgRow`（键值行）、`FgMetric`（统计卡）、`FgBar`（进度条）、`FgCard`（卡片容器）、`FgRecommend`（高亮推荐卡）、`FgButton`（按钮，含 Default/Primary/Danger 三态） |
| `Tabs.ets` | 底部标签枚举 `FgTab` 与短标题数组 `FG_TAB_LABELS`（连接/主页/地图/告警/配送/接管/报告） |

### 7 个屏幕 `entry/src/main/ets/fireguard/screens/`

| 文件 | 对应原型 | 说明 |
| --- | --- | --- |
| `ScreenConnect.ets` | S01 设备连接 | **保留真实 TCP 连接逻辑**（来自原 NetworkSettings）：IP/TCP 端口/视频端口输入、读写 Preferences、连接后进入主页 |
| `ScreenHome.ets` | S02 巡检主页 | 任务总览、电量/待巡检点/烟雾/温度指标卡、推荐动作、进入巡检/手动控制 |
| `ScreenMap.ets` | S03 地图导航 | Stack 绘制的巡检路径图（静态） |
| `ScreenAlert.ets` | S04 告警详情 | 红色告警可视化、识别类型/置信度/温度、处置建议、跳配送/接管 |
| `ScreenDelivery.ets` | S05 应急配送 | 配送物资/路径、进度条、任务状态（静态） |
| `ScreenManual.ets` | S06 手动接管 | **折叠全部真实控制**：实时视频、按钮/摇杆/四轮三种控制模式切换、自动循迹开关、录制、急停 |
| `ScreenReport.ets` | S07 巡检报告 | 巡检耗时/点位/告警指标、事件摘要、导出能力（静态） |

### 主控制台 `entry/src/main/ets/pages/`

| 文件 | 说明 |
| --- | --- |
| `MainConsole.ets` | `@Entry` 页面，承载 7 个屏幕：顶部可滚动内容区 + 底部固定 7 项标签栏。启动**默认进入主页**（`FgTab.Home`），连接小车在「连接」标签内按需操作 |

## 三、修改文件

| 文件 | 改动内容 |
| --- | --- |
| `entry/src/main/ets/entryability/EntryAbility.ets` | 启动页由 `pages/NetworkSettings` 改为 `pages/MainConsole`；调用 `ScreenUtils.setPortrait()` 竖屏 |
| `entry/src/main/ets/utils/ScreenUtils.ets` | 新增 `setPortrait()` 竖屏方法 |
| `entry/src/main/module.json5` | Ability `orientation`：`landscape` → `portrait` |
| `entry/src/main/resources/base/profile/main_pages.json` | 注册新页面 `pages/MainConsole`（置顶） |
| `entry/src/main/resources/base/element/string.json` | 应用名 → `FireGuard` |
| `entry/src/main/resources/zh_CN/element/string.json` | 应用名 → `FireGuard 工业巡检` |
| `entry/src/main/resources/en_US/element/string.json` | 应用名 → `FireGuard` |
| `entry/src/main/resources/base/element/color.json` | `start_window_background` → `#071018`，避免启动白屏闪烁 |
| `build-profile.json5` | 产物签名配置由 `8Ro8SV66...`（缺 `.p7b` 文件）改为 `default`（签名材料完整） |

## 四、编译期修复

改造后用 DevEco 自带 hvigor 工具链编译，修复了 2 处 ArkTS 严格模式报错：

- `ScreenConnect.ets` 与 `ScreenManual.ets` 中 `onTap: () => this.xxx()` 箭头函数
  简写触发 `arkts-no-implicit-return-types`，改为块体 `onTap: () => { this.xxx() }`。

修复后 ArkTS 编译通过、HAP 成功打包（`entry-default-signed.hap`）。

## 五、保留项

原 `NetworkSettings` / `Index` / `MecanumWheel` / `RemoteControl` 页面仍注册且保留，
不再是入口流程，可作参考。底层能力（`tcp/`、`CarUtill/`、`components/`、`Rocker` 库）未改动。

## 六、启动流程

启动 → **主页**（巡检主页）→ 底部标签栏切换各页 → 「连接」页连小车成功后自动回主页。

## 七、v2 升级改造（2025-07）

本次升级将 7 标签页重构为 **5 标签页**，新增 REST API 后端支持、横屏手动接管页面和编队管理标签。

### 关键决策

1. 标签从 7 项（连接/主页/地图/告警/配送/接管/报告）缩减为 **5 项**（连接/主页/告警/配送/编队）
2. 手动接管从竖屏标签页变为**独立横屏全屏页面**（`router.pushUrl` 导航）
3. 新增后端类型开关：**TCP 二进制协议**（兼容旧车）与 **REST API**（Flask `api_server.py:5000` HTTP/JSON）可切换
4. 地图、报告、手动接管（竖屏）标签页从导航移除，源文件保留作参考

### 新增文件

| 文件 | 说明 |
| --- | --- |
| `entry/src/main/ets/CarUtill/BackendType.ets` | `BackendType` 枚举（TCP=0, REST=1）、`BackendState` 全局静态类（类型、连接状态、IP、端口） |
| `entry/src/main/ets/tcp/RestApiClient.ets` | REST API 单例客户端：`initConnection`、`sendMove`、`sendMoveContinuous`、`checkHealth`、`getStatus` |
| `entry/src/main/ets/components/ViewRockerComponents.ets` | 视角/云台摇杆占位组件（`tiltWidth: 0.4`），当前仅输出调试日志 |
| `entry/src/main/ets/fireguard/screens/ScreenFleet.ets` | 编队管理标签：车辆列表（1 领航 + 2 从车）、添加从车按钮、编队命令（出发/停止）、解散编队、编队统计 |
| `entry/src/main/ets/pages/ScreenManualLandscape.ets` | `@Entry` 横屏手动接管页面：全屏 Stack 布局、视频背景、雷达、运动摇杆（左下 120×120）、视角摇杆（右下 140×62）、右侧工具列（灯/麦/录/雷/图）、底部急停/后退/速度显示 |
| `entry/src/main/resources/base/profile/main_pages.json` | 注册 `pages/ScreenManualLandscape` 页面 |

### 修改文件

| 文件 | 改动 |
| --- | --- |
| `Tabs.ets` | `FgTab` 从 7 项缩减为 5 项（Connect/Home/Alert/Delivery/Fleet），标签文字同步更新 |
| `MainConsole.ets` | 移除 `ScreenMap`/`ScreenReport`/`ScreenManual` 导入和渲染，新增 `ScreenFleet`，`tabList` 更新为 5 项 |
| `PreferencesUtils.ets` | `NetInfoPreferencesUtils` 新增 `KEY_BACKEND_TYPE`、`KEY_REST_PORT` 及对应的 getter/setter |
| `CarApi.ets` | `carBtnCtrl` 新增后端路由（REST 时映射 `CarDirection` → REST 命令字符串并 POST）；新增 `sendRestMove`/`sendRestMoveContinuous`/`sendRestStop` 方法 |
| `CarRockerComponents.ets` | 新增 REST 模式轮询逻辑：XY→方向映射、死区（<15 停止）、速度计算（20-100）、`setInterval(300ms)` 持续发送；`aboutToDisappear` 清理 timer |
| `ScreenConnect.ets` | 新增 TCP/REST 后端类型切换按钮、REST 端口输入字段、`initRestConfig` 连接方法；连接成功后设置 `BackendState`；读写首选项新增后端类型和 REST 端口 |
| `ScreenHome.ets` | 替换硬编码布局为状态化布局：已连接时显示巡检信息 + "开始巡检"/"切换到手动接管"；未连接时显示连接提示 + "未连接到设备"按钮 |
| `ScreenAlert.ets` | "远程接管"按钮改为 `router.pushUrl('pages/ScreenManualLandscape')` 横屏导航 |

### 保留项（已从导航移除，源文件保留）

- `ScreenMap.ets`、`ScreenReport.ets`、`ScreenManual.ets`：不再出现在 5 标签页中，文件保留作参考
- `ScreenDelivery.ets`：仍为独立标签页，布局未变
- 底层能力（`tcp/`、`CarUtill/CarEncode.ets`、`CarUtill/CarEnum.ets`、`CarBtnComponents.ets`、`VideoComponents.ets`、Rocker 库）：未改动

### 运行时行为

- TCP 模式：摇杆走 `CarEncode.CtrlCarEncode` → TCP 二进制发送；按钮走 `CarEncode.ButtonCarEncode` → TCP 发送
- REST 模式：摇杆走 XY→方向映射 + 轮询 → `POST /api/move`（每 300ms 持续发送）；按钮走 `CarDirection` → REST 命令映射 → `POST /api/move`（带 duration）；急停走 `POST /api/move (stop)`
- 横屏接管页进入时 `ScreenUtils.setLandscape()`，退出时 `ScreenUtils.setPortrait()` 恢复竖屏
