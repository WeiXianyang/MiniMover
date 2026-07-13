import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

/// FireGuard 自定义图标 — 所有 SVG 来自 page-prototype-spec 分支 icon 资源库
class AppIcons {
  AppIcons._();

  static const _base = 'assets/icons';

  // ── Tab 栏 ──
  static Widget plug({double size = 22, Color? color}) =>
      _icon('$_base/plug.svg', size, color);
  static Widget home({double size = 22, Color? color}) =>
      _icon('$_base/home.svg', size, color);
  static Widget triangleAlert({double size = 22, Color? color}) =>
      _icon('$_base/triangle-alert.svg', size, color);
  static Widget route({double size = 22, Color? color}) =>
      _icon('$_base/route.svg', size, color);
  static Widget car({double size = 22, Color? color}) =>
      _icon('$_base/car.svg', size, color);

  // ── 功能按钮 ──
  static Widget settings({double size = 18, Color? color}) =>
      _icon('$_base/settings.svg', size, color);
  static Widget lightbulb({double size = 18, Color? color}) =>
      _icon('$_base/lightbulb.svg', size, color);
  static Widget mic({double size = 18, Color? color}) =>
      _icon('$_base/mic.svg', size, color);
  static Widget record({double size = 18, Color? color}) =>
      _icon('$_base/record.svg', size, color);
  static Widget radar({double size = 18, Color? color}) =>
      _icon('$_base/radar.svg', size, color);
  static Widget map({double size = 18, Color? color}) =>
      _icon('$_base/map.svg', size, color);
  static Widget arrowLeft({double size = 18, Color? color}) =>
      _icon('$_base/arrow-left.svg', size, color);
  static Widget octagonAlert({double size = 18, Color? color}) =>
      _icon('$_base/octagon-alert.svg', size, color);

  // ── 编队命令 ──
  static Widget play({double size = 18, Color? color}) =>
      _icon('$_base/play.svg', size, color);
  static Widget square({double size = 18, Color? color}) =>
      _icon('$_base/square.svg', size, color);
  static Widget unlink({double size = 18, Color? color}) =>
      _icon('$_base/unlink.svg', size, color);
  static Widget save({double size = 18, Color? color}) =>
      _icon('$_base/save.svg', size, color);
  static Widget move({double size = 18, Color? color}) =>
      _icon('$_base/move.svg', size, color);
  static Widget rotateCcw({double size = 18, Color? color}) =>
      _icon('$_base/rotate-ccw.svg', size, color);
  static Widget signal({double size = 18, Color? color}) =>
      _icon('$_base/signal.svg', size, color);

  static Widget _icon(String asset, double size, Color? color) {
    return SvgPicture.asset(
      asset,
      width: size,
      height: size,
      colorFilter: color != null
          ? ColorFilter.mode(color, BlendMode.srcATop)
          : null,
    );
  }
}
