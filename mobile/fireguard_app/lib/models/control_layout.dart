import 'package:flutter/material.dart';

/// 组件类型
enum ControlComponent {
  moveJoystick,
  viewJoystick,
  btnLight,
  btnMic,
  btnRecord,
  btnMap,
  btnEmergencyStop,
  btnSpeed,
  btnBack,
  topBar,
}

/// 单个组件的布局配置
class ComponentConfig {
  final ControlComponent type;
  final String label;
  double x; // 百分比 0~1 (相对于父容器)
  double y;
  double width;
  double height;
  double opacity;
  bool visible;

  ComponentConfig({
    required this.type,
    required this.label,
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    this.opacity = 1.0,
    this.visible = true,
  });

  /// 复制
  ComponentConfig copyWith({
    double? x,
    double? y,
    double? width,
    double? height,
    double? opacity,
    bool? visible,
  }) {
    return ComponentConfig(
      type: type,
      label: label,
      x: x ?? this.x,
      y: y ?? this.y,
      width: width ?? this.width,
      height: height ?? this.height,
      opacity: opacity ?? this.opacity,
      visible: visible ?? this.visible,
    );
  }

  /// 深拷贝
  ComponentConfig clone() {
    return ComponentConfig(
      type: type, label: label,
      x: x, y: y, width: width, height: height,
      opacity: opacity, visible: visible,
    );
  }

  /// 从百分比转成像素位置
  Offset toOffset(Size parentSize) =>
      Offset(x * parentSize.width, y * parentSize.height);

  /// 从百分比转成像素尺寸
  Size toSize(Size parentSize) =>
      Size(width * parentSize.width, height * parentSize.height);

  /// 拖拽时更新位置（从像素转百分比）
  void updateFromOffset(Offset pixel, Size parentSize) {
    x = (pixel.dx / parentSize.width).clamp(0.0, 1.0);
    y = (pixel.dy / parentSize.height).clamp(0.0, 1.0);
  }
}

/// 完整的控制布局（所有组件的默认值）
class ControlLayout {
  late ComponentConfig moveJoystick;
  late ComponentConfig viewJoystick;
  late ComponentConfig btnLight;
  late ComponentConfig btnMic;
  late ComponentConfig btnRecord;
  late ComponentConfig btnMap;
  late ComponentConfig btnEmergencyStop;
  late ComponentConfig btnSpeed;
  late ComponentConfig btnBack;
  late ComponentConfig topBar;

  ControlLayout() {
    initDefaults();
  }

  void initDefaults() {
    // 左摇杆
    moveJoystick = ComponentConfig(
      type: ControlComponent.moveJoystick,
      label: '移动摇杆',
      x: 0.035,
      y: 0.55,
      width: 0.14, // 120/876 ≈ 0.137
      height: 0.41, // 160/390 ≈ 0.41
    );

    // 右摇杆
    viewJoystick = ComponentConfig(
      type: ControlComponent.viewJoystick,
      label: '视角摇杆',
      x: 0.73,
      y: 0.58,
      width: 0.16, // 140/876
      height: 0.20, // 80/390
    );

    // 灯光按钮
    btnLight = ComponentConfig(
      type: ControlComponent.btnLight,
      label: '灯光',
      x: 0.935,
      y: 0.15,
      width: 0.048, // 42/876
      height: 0.108, // 42/390
    );

    // 麦克风
    btnMic = ComponentConfig(
      type: ControlComponent.btnMic,
      label: '麦克风',
      x: 0.935,
      y: 0.28,
      width: 0.048,
      height: 0.108,
    );

    // 录制
    btnRecord = ComponentConfig(
      type: ControlComponent.btnRecord,
      label: '录制',
      x: 0.935,
      y: 0.41,
      width: 0.048,
      height: 0.108,
    );

    // 地图
    btnMap = ComponentConfig(
      type: ControlComponent.btnMap,
      label: '地图',
      x: 0.935,
      y: 0.55,
      width: 0.053, // 46/876
      height: 0.118, // 46/390
    );

    // 急停
    btnEmergencyStop = ComponentConfig(
      type: ControlComponent.btnEmergencyStop,
      label: '急停',
      x: 0.43,
      y: 0.84,
      width: 0.13, // 116/876
      height: 0.108, // 42/390
    );

    // 速度
    btnSpeed = ComponentConfig(
      type: ControlComponent.btnSpeed,
      label: '速度',
      x: 0.58,
      y: 0.85,
      width: 0.08, // 72/876
      height: 0.082, // 32/390
    );

    // 返回
    btnBack = ComponentConfig(
      type: ControlComponent.btnBack,
      label: '返回',
      x: 0.31,
      y: 0.85,
      width: 0.07, // ~60px, 够放图标+"返回"
      height: 0.092, // 36/390
    );

    // 顶部信息栏
    topBar = ComponentConfig(
      type: ControlComponent.topBar,
      label: '状态栏',
      x: 0,
      y: 0,
      width: 1.0,
      height: 0.14,
    );
  }

  List<ComponentConfig> get all => [
        moveJoystick,
        viewJoystick,
        btnLight,
        btnMic,
        btnRecord,
        btnMap,
        btnEmergencyStop,
        btnSpeed,
        btnBack,
        topBar,
      ];

  /// 深拷贝整个布局（用于设置页编辑，不保存不生效）
  ControlLayout clone() {
    final copy = ControlLayout();
    copy.moveJoystick = moveJoystick.clone();
    copy.viewJoystick = viewJoystick.clone();
    copy.btnLight = btnLight.clone();
    copy.btnMic = btnMic.clone();
    copy.btnRecord = btnRecord.clone();
    copy.btnMap = btnMap.clone();
    copy.btnEmergencyStop = btnEmergencyStop.clone();
    copy.btnSpeed = btnSpeed.clone();
    copy.btnBack = btnBack.clone();
    copy.topBar = topBar.clone();
    return copy;
  }

  /// 从另一个 layout 复制所有值
  void copyFrom(ControlLayout other) {
    moveJoystick = other.moveJoystick.clone();
    viewJoystick = other.viewJoystick.clone();
    btnLight = other.btnLight.clone();
    btnMic = other.btnMic.clone();
    btnRecord = other.btnRecord.clone();
    btnMap = other.btnMap.clone();
    btnEmergencyStop = other.btnEmergencyStop.clone();
    btnSpeed = other.btnSpeed.clone();
    btnBack = other.btnBack.clone();
    topBar = other.topBar.clone();
  }

  ComponentConfig? findByType(ControlComponent type) {
    try {
      return all.firstWhere((c) => c.type == type);
    } catch (_) {
      return null;
    }
  }

  /// 从 Map 恢复（用于持久化）
  Map<String, Map<String, double>> toJson() {
    final map = <String, Map<String, double>>{};
    for (final c in all) {
      map[c.type.name] = {
        'x': c.x,
        'y': c.y,
        'width': c.width,
        'height': c.height,
        'opacity': c.opacity,
      };
    }
    return map;
  }

  /// 从 Map 加载
  void fromJson(Map<String, dynamic> json) {
    for (final c in all) {
      final data = json[c.type.name];
      if (data is Map) {
        c.x = (data['x'] as num?)?.toDouble() ?? c.x;
        c.y = (data['y'] as num?)?.toDouble() ?? c.y;
        c.width = (data['width'] as num?)?.toDouble() ?? c.width;
        c.height = (data['height'] as num?)?.toDouble() ?? c.height;
        c.opacity = (data['opacity'] as num?)?.toDouble() ?? c.opacity;
      }
    }
  }
}
