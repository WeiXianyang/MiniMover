import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// 统一的页面外壳：居中 + 返回按钮 + 渐变背景
class PageShell extends StatelessWidget {
  final Widget child;
  final String? title;
  final VoidCallback? onBack;

  const PageShell({
    super.key,
    required this.child,
    this.title,
    this.onBack,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bgGradientTop,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppTheme.textPrimary),
          onPressed: onBack ?? () => Navigator.of(context).pop(),
        ),
        title: title != null
            ? Text(title!, style: AppTheme.pageTitle)
            : null,
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppTheme.bgGradientTop, AppTheme.bgGradientBottom],
          ),
        ),
        child: child,
      ),
    );
  }
}
