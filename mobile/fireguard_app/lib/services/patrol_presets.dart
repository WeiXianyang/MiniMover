import '../services/nav_service.dart';

/// 预设巡检点
class PresetPoint {
  final String name;
  final double x;
  final double y;
  final String source; // 'static' | 'route'
  final String? routeName; // 来源路线名（仅 source=='route' 时有效）

  const PresetPoint({
    required this.name,
    required this.x,
    required this.y,
    this.source = 'static',
    this.routeName,
  });

  PresetPoint copyWith({String? name, double? x, double? y}) => PresetPoint(
        name: name ?? this.name,
        x: x ?? this.x,
        y: y ?? this.y,
        source: source,
        routeName: routeName,
      );

  /// 两个点是否视为重复（坐标差 < 0.3m）
  bool isCloseTo(PresetPoint other) {
    final dx = (x - other.x).abs();
    final dy = (y - other.y).abs();
    return dx < 0.3 && dy < 0.3;
  }

  @override
  bool operator ==(Object other) =>
      other is PresetPoint && other.name == name && other.x == x && other.y == y && other.source == source;

  @override
  int get hashCode => Object.hash(name, x, y, source);
}

/// ═══ 静态预设点 — 直接改此数组即可增删改坐标 ═══
/// 坐标从车端巡逻控制台 http://<IP>:5000/nav/patrol 点地图获取
const PRESET_POINTS = <PresetPoint>[
  PresetPoint(name: '配电柜A', x: -1.0, y: 1.5),
  PresetPoint(name: '配电柜B', x: 0.5, y: 1.8),
  PresetPoint(name: '仓储通道', x: 2.0, y: 0.0),
  PresetPoint(name: '消防器材点', x: -2.0, y: -0.5),
  PresetPoint(name: '充电待命点', x: 0.0, y: 0.0),
  PresetPoint(name: '应急物资点D', x: 1.5, y: -1.2),
];

/// 从车端路线途经点自动提取为预设点
List<PresetPoint> pointsToPresets(List<NavPoint> points, {String routeName = ''}) {
  return points.asMap().entries.map((e) {
    return PresetPoint(
      name: routeName.isNotEmpty ? '$routeName-${e.key + 1}' : '途经点${e.key + 1}',
      x: e.value.x,
      y: e.value.y,
      source: 'route',
      routeName: routeName,
    );
  }).toList();
}

/// 两路数据合并：静态优先，坐标差 < 0.3m 自动去重
List<PresetPoint> mergePresets(List<PresetPoint> staticPoints, List<PresetPoint> routePoints) {
  final merged = <PresetPoint>[...staticPoints];
  for (final rp in routePoints) {
    final dup = merged.any((sp) => sp.isCloseTo(rp));
    if (!dup) merged.add(rp);
  }
  return merged;
}
