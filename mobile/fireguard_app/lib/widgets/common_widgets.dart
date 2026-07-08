import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// 毛玻璃卡片 — 对应 Figma 中的 card 组件
class GlassCard extends StatelessWidget {
  final Widget child;
  final double? height;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;

  const GlassCard({
    super.key,
    required this.child,
    this.height,
    this.padding,
    this.margin,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: AppTheme.cardWidth,
      height: height,
      margin: margin,
      padding: padding ?? const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.cardFill,
        borderRadius: BorderRadius.circular(AppTheme.cardRadius),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: child,
    );
  }
}

/// 渐变主按钮
class GradientButton extends StatelessWidget {
  final String text;
  final VoidCallback? onTap;
  final bool secondary;

  const GradientButton({
    super.key,
    required this.text,
    this.onTap,
    this.secondary = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: AppTheme.cardWidth,
        height: AppTheme.btnHeight,
        decoration: BoxDecoration(
          gradient: secondary
              ? null
              : const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: AppTheme.btnGradient,
                ),
          borderRadius: BorderRadius.circular(AppTheme.btnRadius),
          border: secondary
              ? Border.all(color: AppTheme.cardBorder)
              : null,
        ),
        alignment: Alignment.center,
        child: Text(
          text,
          style: secondary ? AppTheme.btnTextSecondary : AppTheme.btnText,
        ),
      ),
    );
  }
}

/// 小按钮 (用于双按钮排列)
class SmallButton extends StatelessWidget {
  final String text;
  final VoidCallback? onTap;

  const SmallButton({super.key, required this.text, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 157,
        height: AppTheme.smallBtnHeight,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AppTheme.btnRadius),
          border: Border.all(color: AppTheme.cardBorder),
        ),
        alignment: Alignment.center,
        child: Text(text, style: AppTheme.btnTextSecondary),
      ),
    );
  }
}

/// 状态标签 (如"最近在线")
class StatusBadge extends StatelessWidget {
  final String text;
  final bool active;

  const StatusBadge({super.key, required this.text, this.active = true});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppTheme.cardFill,
        borderRadius: BorderRadius.circular(13),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: active ? AppTheme.statusGreen : AppTheme.statusRed,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          Text(text, style: AppTheme.bodyValue.copyWith(fontSize: 12)),
        ],
      ),
    );
  }
}

/// 信息行 (标签: 值)
class InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final bool valueBold;

  const InfoRow({
    super.key,
    required this.label,
    required this.value,
    this.valueBold = true,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: AppTheme.bodyLabel),
          Text(
            value,
            style: valueBold ? AppTheme.bodyValue : AppTheme.bodyLabel,
            textAlign: TextAlign.right,
          ),
        ],
      ),
    );
  }
}

/// 统计数值卡片
class StatBlock extends StatelessWidget {
  final String value;
  final String label;
  final IconData? icon;

  const StatBlock({
    super.key,
    required this.value,
    required this.label,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (icon != null)
          Icon(icon, color: AppTheme.accent, size: 22),
        const SizedBox(height: 4),
        Text(value, style: AppTheme.statValue),
        const SizedBox(height: 4),
        Text(label, style: AppTheme.statLabel),
      ],
    );
  }
}

/// 页面标题栏
class PageHeader extends StatelessWidget {
  final String title;
  final String subTitle;
  final String badgeText;
  final bool badgeActive;

  const PageHeader({
    super.key,
    required this.title,
    required this.subTitle,
    this.badgeText = '',
    this.badgeActive = true,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(title, style: AppTheme.pageTitle),
            if (badgeText.isNotEmpty)
              StatusBadge(text: badgeText, active: badgeActive),
          ],
        ),
        const SizedBox(height: 4),
        Text(subTitle, style: AppTheme.subtitle),
      ],
    );
  }
}
