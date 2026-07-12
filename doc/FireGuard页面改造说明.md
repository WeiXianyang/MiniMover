# FireGuard 工业巡检 APP 页面改造说明

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
