import 'package:flutter/material.dart';

/// FireGuard 设计系统 — 所有 token 从 Figma API 精确提取
class AppTheme {
  AppTheme._();

  // ── 颜色 ──────────────────────────────────────────
  static const Color accent = Color(0xFFFF8C42);
  static const Color accentLight = Color(0xFFFFB870);
  static const Color textPrimary = Color(0xFFEEF4FF);
  static const Color textSecondary = Color(0xFF9AA8BF);
  static const Color textDark = Color(0xFF10151D);
  static const Color statusGreen = Color(0xFF2DCF9F);
  static const Color statusRed = Color(0xFFFF4D4D);
  static const Color cardFill = Color.fromRGBO(255, 255, 255, 0.04);
  static const Color cardBorder = Color.fromRGBO(255, 255, 255, 0.07);
  static const Color dividerLine = Color.fromRGBO(255, 255, 255, 0.08);

  // 背景渐变 (从 Figma 提取)
  static const Color bgGradientTop = Color(0xFF090E16);
  static const Color bgGradientMid = Color(0xFF0D1117);
  static const Color bgGradientBottom = Color(0xFF121824);

  // 手机 Frame 渐变
  static const Color frameGradientTop = Color(0xFF111A27);
  static const Color frameGradientBottom = Color(0xFF0B1220);

  // 按钮渐变
  static const List<Color> btnGradient = [accent, accentLight];

  // ── 尺寸 ──────────────────────────────────────────
  static const double phoneWidth = 390.0;
  static const double phoneHeight = 876.0;
  static const double cardWidth = 326.0;
  static const double pagePadding = 32.0;
  static const double cardRadius = 12.0;
  static const double btnRadius = 8.0;
  static const double btnHeight = 52.0;
  static const double smallBtnHeight = 48.0;
  static const double iconSize = 24.0;

  // ── 字体 (默认系统字体, 后续可替换为 Inter) ─────
  static const TextStyle pageTitle = TextStyle(
    fontWeight: FontWeight.w700,
    fontSize: 20,
    color: textPrimary,
  );

  static const TextStyle subtitle = TextStyle(
    fontWeight: FontWeight.w400,
    fontSize: 12,
    color: textSecondary,
  );

  static const TextStyle sectionLabel = TextStyle(
    fontWeight: FontWeight.w700,
    fontSize: 14,
    color: accent,
  );

  static const TextStyle bodyValue = TextStyle(
    fontWeight: FontWeight.w700,
    fontSize: 13,
    color: textPrimary,
  );

  static const TextStyle bodyLabel = TextStyle(
    fontWeight: FontWeight.w400,
    fontSize: 13,
    color: textSecondary,
  );

  static const TextStyle statValue = TextStyle(
    fontWeight: FontWeight.w700,
    fontSize: 20,
    color: textPrimary,
  );

  static const TextStyle statLabel = TextStyle(
    fontWeight: FontWeight.w400,
    fontSize: 12,
    color: textSecondary,
  );

  static const TextStyle btnText = TextStyle(
    fontWeight: FontWeight.w700,
    fontSize: 15,
    color: textDark,
  );

  static const TextStyle btnTextSecondary = TextStyle(
    fontWeight: FontWeight.w700,
    fontSize: 15,
    color: textPrimary,
  );

  // ── ThemeData ─────────────────────────────────────
  static ThemeData get darkTheme => ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: bgGradientTop,
        colorScheme: const ColorScheme.dark(
          primary: accent,
          secondary: accentLight,
          surface: Color(0xFF0D1117),
        ),
      );
}
