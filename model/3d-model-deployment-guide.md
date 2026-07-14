# 3D 模型部署教程

本教程说明如何将小车 3D 模型导出为 GLB 并部署到 FireGuard Flutter 应用中。

---

## 1. 模型导出（Blender → GLB）

### 1.1 准备工作

在 Blender 中打开小车模型，确保：

- 应用所有变换：选中所有物体 → `Ctrl + A` → **全部变换**
- 将原点设置到几何中心或模型底部中央
- 模型主方向：**车头朝向 +Y 或 +Z**

### 1.2 命名部件（关键！）

在 Blender 的 **大纲视图（Outliner）** 中，对需要交互的部件 Mesh 进行规范命名：

| 部件 | 推荐命名 | 当前模型命名 |
|------|---------|-------------|
| 激光雷达 | `lidar_link` | `laser_link` |
| 深度相机 | `camera_link` | `camera_link` |
| 车前灯 | `headlight_xxx` | `Cylinder003`, `Cylinder009` |
| 驱动轮组 | `wheel_fl`, `wheel_fr` 等 | `front_left_wheel`, `back_left_wheel` |

> **注意**：名称会决定点击时能否正确识别。不要用 Blender 默认名如 `Cube.001`、`Cylinder`。

### 1.3 导出 GLB

1. `文件 → 导出 → glTF 2.0 (.glb/.gltf)`
2. 格式选择 **glTF Binary (.glb)**
3. 勾选：**Selected Objects**（仅导出选中的）、**Apply Modifiers**、**Compress**
4. 导出为 `car.glb`

---

## 2. 部署到 Flutter 项目

### 2.1 放置文件

将 `.glb` 文件放到：

```
mobile/fireguard_app/assets/models/car.glb
```

确认 `pubspec.yaml` 已注册目录：

```yaml
flutter:
  assets:
    - assets/models/
```

### 2.2 验证 mesh 名

运行 App 后进入 3D 模型页，打开终端日志，查找：

```
=== Model mesh names: ok|["base_link","laser_link",...]
```

记下所有 mesh 名称，与预期部件进行对照。

> 如日志未出现，确认 `model3d_page.dart` 中 `modelLoaded` 回调已添加 `debugPrint`。

---

## 3. 更新代码中的部件映射

### 3.1 打开文件

`mobile/fireguard_app/lib/pages/model3d_page.dart`

### 3.2 更新 Dart 端匹配（`_matchPart` 方法）

找到以下代码块，在对应部件行添加新的 mesh 名关键词：

```dart
String? _matchPart(String name) {
    final lower = name.toLowerCase();
    for (final p in _parts) {
      if (lower.contains(p.id)) return p.id;
    }
    // ↓ 在这里添加/修改 mesh 名映射
    if (lower.contains('lidar') || lower.contains('laser_link')) return 'lidar';
    if (lower.contains('camera')) return 'camera';
    if (lower.contains('cylinder') || lower.contains('headlight')) return 'light';
    if (lower.contains('wheel') || lower.contains('左') || lower.contains('右')) return 'wheel';
    return null;
  }
```

### 3.3 更新 JS 端高亮（`highlightPart` 函数）

在同文件中搜索 `window.highlightPart`，更新对应的 mesh 名匹配：

```javascript
if (lower === 'lidar' && nl.includes('laser_link')) out.push(n);
if (lower === 'light' && (nl.includes('cylinder003') || nl.includes('cylinder009') || nl.includes('headlight'))) out.push(n);
if (lower === 'wheel' && (nl.includes('wheel') || nl.includes('左') || nl.includes('右'))) out.push(n);
```

### 3.4 更新部件详情（可选）

修改 `_parts` 静态列表以更新部件名称、型号、规格：

```dart
static const _parts = [
    _PartInfo('lidar', '激光雷达', 'RPLIDAR A1', '360° 激光扫描测距',
        ['范围: 0.15m – 12m', '频率: 8000 次/秒', '状态: ● 正常']),
    _PartInfo('camera', '深度相机', 'Astra Pro Plus', '深度 + RGB 双目',
        ['分辨率: 1280×720 @30fps', '深度: 0.6m – 8m', '状态: ● 正常']),
    _PartInfo('light', '车前灯', 'LED 矩阵大灯', '可编程 RGB 灯组',
        ['亮度: 0 – 100% 可调', '模式: 常亮 · 闪烁 · 呼吸', '状态: ● 正常']),
    _PartInfo('wheel', '驱动轮组', '麦克纳姆轮组 ×4', '独立悬挂 · 全向移动',
        ['电机: 编码器减速 ×4', '转速: 160 RPM', '状态: ● 正常']),
  ];
```

---

## 4. 测试验证

1. 重新构建并运行：

```bash
flutter clean && flutter run -d <设备ID>
```

2. 进入 3D 模型页面
3. 依次点击四个部件，验证：
   - 点击后部件**橙色高亮**
   - 右侧面板**显示对应部件信息**
   - 点击返回按钮 `←` **取消高亮**，回到概览
   - 点击其他部件**自动切换**
   - 自动旋转 / 重置视角功能正常

---

## 5. 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 部件无法高亮 | mesh 名与代码中映射不匹配 | 查看终端日志确认 mesh 名，更新映射 |
| 模型太大/太小 | Blender 中模型比例问题 | 导出前统一缩放到合适尺寸，或调整代码中 `camera.position` |
| 页面白屏/加载失败 | GLB 文件未放入正确路径 | 确认 `assets/models/car.glb` 存在且已 `flutter clean` |
| 高亮后无法取消 | `clearHighlight` 未生效 | 确认当前版本使用 `_hl` 全局数组方案，而非 `material.clone()` |

---

## 6. 自定义部件

如需新增部件（如舵机臂、天线等）：

1. 在 Blender 中给 mesh 命名（如 `arm_link`）
2. 在 `_parts` 列表中添加新的 `_PartInfo`
3. 在 `_matchPart` 中添加 `lower.contains('arm') → 'arm'`
4. 在 `highlightPart` JS 中添加对应的匹配规则
5. 在 `_partIcon` 中添加对应图标
