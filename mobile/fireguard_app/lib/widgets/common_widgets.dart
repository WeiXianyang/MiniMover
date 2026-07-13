import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// 卡片 — 对齐 prototype .card / .metric
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
      width: double.infinity,
      height: height,
      margin: margin,
      padding: padding ?? const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppTheme.cardFill,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: child,
    );
  }
}

/// 渐变主按钮 — 对齐 prototype .btn.primary
class GradientButton extends StatelessWidget {
  final String text;
  final VoidCallback? onTap;
  final bool secondary;
  final Widget? icon;

  const GradientButton({
    super.key,
    required this.text,
    this.onTap,
    this.secondary = false,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        height: AppTheme.btnHeight,
        decoration: BoxDecoration(
          color: secondary ? AppTheme.btnSecondaryBg : AppTheme.accent,
          borderRadius: BorderRadius.circular(9),
          border: secondary
              ? Border.all(color: AppTheme.cardBorder)
              : null,
        ),
        alignment: Alignment.center,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[icon!, const SizedBox(width: 8)],
            Text(
              text,
              style: TextStyle(
                fontWeight: FontWeight.w800,
                fontSize: 15,
                color: secondary ? AppTheme.textPrimary : AppTheme.textDark,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 小按钮 — 对齐 prototype .btn
class SmallButton extends StatelessWidget {
  final String text;
  final VoidCallback? onTap;

  const SmallButton({super.key, required this.text, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        height: AppTheme.smallBtnHeight,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(9),
          color: AppTheme.btnSecondaryBg,
        ),
        alignment: Alignment.center,
        child: Text(text, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: AppTheme.textPrimary)),
      ),
    );
  }
}

/// 状态标签 — 对齐 prototype .pill
class StatusBadge extends StatelessWidget {
  final String text;
  final bool active;

  const StatusBadge({super.key, required this.text, this.active = true});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
      decoration: BoxDecoration(
        color: active
            ? const Color.fromRGBO(99, 230, 167, 0.14)
            : const Color.fromRGBO(255, 101, 112, 0.2),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w800,
          color: active ? const Color(0xFFDCFFF0) : const Color(0xFFFFF2F3),
        ),
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

/// 统计数值卡片 — 对齐 prototype .metric
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
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(value, style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
        const SizedBox(height: 8),
        Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
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
