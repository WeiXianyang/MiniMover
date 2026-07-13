import 'package:flutter/material.dart';

/// FireGuard 设计系统 — 与 page-prototype-spec 分支 styles.css 同步
class AppTheme {
  AppTheme._();

  // ── 颜色（对齐 prototype :root 变量）─────
  static const Color accent = Color(0xFFE88B45);       // --orange
  static const Color accentLight = Color(0xFFFFB870);
  static const Color cyan = Color(0xFF5BAEC7);          // --cyan
  static const Color textPrimary = Color(0xFFEEF4FF);   // --text
  static const Color textSecondary = Color(0xFF8997A8); // --muted
  static const Color textDark = Color(0xFF10151D);
  static const Color statusGreen = Color(0xFF58B98E);   // --green
  static const Color statusRed = Color(0xFFD85B64);     // --red

  // 面板/分割线（对齐 prototype）
  static const Color panelBg = Color(0xFF151F2B);       // --panel
  static const Color panelLine = Color(0xFF263241);     // --line
  static const Color panelBg2 = Color(0xFF1B2633);      // --panel-2
  static const Color cardFill = Color.fromRGBO(24, 37, 55, 0.9);
  static const Color cardBorder = Color(0xFF263241);
  static const Color dividerLine = Color.fromRGBO(147, 164, 186, 0.18);

  // 背景渐变
  static const Color bgGradientTop = Color(0xFF080D13);  // --bg
  static const Color phoneBg = Color(0xFF101821);        // --phone
  static const Color bgGradientBottom = Color(0xFF121824);

  // 手机 Frame 渐变
  static const Color frameGradientTop = Color(0xFF111A27);
  static const Color frameGradientBottom = Color(0xFF090E14);

  // 按钮渐变
  static const List<Color> btnGradient = [accent, accentLight];

  // 次要按钮背景（prototype .btn）
  static const Color btnSecondaryBg = Color(0xFF28384B);

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
  static const double tabBarInset = 84.0; // 底部栏高度 + 安全间距

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
