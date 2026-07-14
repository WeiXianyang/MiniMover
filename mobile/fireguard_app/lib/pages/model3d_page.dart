import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart' show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/app_icons.dart';

/// S09 – 3D 模型展示 (横屏)
/// Android/iOS: WebView + Three.js 真实 GLB 渲染
/// Web/Desktop: CustomPaint 线框回退
class Model3DPage extends StatefulWidget {
  final CarState carState;
  const Model3DPage({super.key, required this.carState});

  @override
  State<Model3DPage> createState() => _Model3DPageState();
}

class _Model3DPageState extends State<Model3DPage>
    with SingleTickerProviderStateMixin {
  // WebView 相关
  WebViewController? _wvc;
  bool _webViewAvailable = false;
  bool _webViewReady = false;

  String? _selectedPart;
  String _rawPartName = '';
  bool _autoRotate = false;
  bool _loading = true;
  String? _error;

  // Animation for wireframe fallback
  late final AnimationController _ac;
  double _rotation = 0;

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

  @override
  void initState() {
    super.initState();
    _ac = AnimationController(vsync: this, duration: const Duration(seconds: 20));
    _lockLandscape();
    _initView();
  }

  @override
  void dispose() {
    _ac.dispose();
    _restoreOrientation();
    super.dispose();
  }

  void _lockLandscape() {
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  void _restoreOrientation() {
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  }

  bool get _isMobile => !kIsWeb && defaultTargetPlatform == TargetPlatform.android ||
      defaultTargetPlatform == TargetPlatform.iOS;

  Future<void> _initView() async {
    if (_isMobile) {
      await _initWebView();
    } else {
      setState(() => _loading = false);
    }
  }

  Future<void> _initWebView() async {
    try {
      // 延迟导入 webview_flutter，避免 web/desktop 编译报错
      final wv = await _createWebViewController();
      if (wv != null) {
        setState(() { _wvc = wv; _webViewAvailable = true; });
      } else {
        setState(() => _loading = false);
      }
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<WebViewController?> _createWebViewController() async {
    try {
      final bytes = await rootBundle.load('assets/models/car.glb');
      final b64 = base64Encode(bytes.buffer.asUint8List());
      final html = _buildHtml(b64);

      return WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setBackgroundColor(const Color(0xFF0B121C))
        ..addJavaScriptChannel('partSelected', onMessageReceived: (msg) {
          final name = msg.message;
          final matched = _matchPart(name);
          if (matched != null) {
            setState(() {
              _rawPartName = name;
              _selectedPart = matched;
              _loading = false;
              _webViewReady = true;
            });
            _wvc?.runJavaScript('highlightPart("$matched")');
          }
        })
        ..addJavaScriptChannel('modelLoaded', onMessageReceived: (_) {
          setState(() { _loading = false; _webViewReady = true; });
        })
        ..loadHtmlString(html);
    } catch (_) {
      return null;
    }
  }

  String? _matchPart(String name) {
    final lower = name.toLowerCase();
    for (final p in _parts) {
      if (lower.contains(p.id)) return p.id;
    }
    // 模型特定 mesh 名映射
    if (lower.contains('lidar') || lower.contains('radar') || lower.contains('scan') || lower.contains('laser_link')) return 'lidar';
    if (lower.contains('camera') || lower.contains('cam') || lower.contains('depth')) return 'camera';
    if (lower.contains('cylinder') || lower.contains('silver_rim') || lower.contains('light') || lower.contains('lamp') || lower.contains('led') || lower.contains('head')) return 'light';
    if (lower.contains('wheel') || lower.contains('tire') || lower.contains('麦轮')) return 'wheel';
    return null;
  }

  _PartInfo? get _info => _parts.cast<_PartInfo?>().firstWhere(
      (p) => p!.id == _selectedPart, orElse: () => null);

  void _toggleRotate() {
    _autoRotate = !_autoRotate;
    if (_webViewAvailable) {
      _wvc?.runJavaScript('toggleAutoRotate($_autoRotate)');
    } else {
      if (_autoRotate) {
        _ac.repeat();
      } else {
        _ac.stop();
      }
    }
    setState(() {});
  }

  void _resetView() {
    if (_webViewAvailable) {
      _wvc?.runJavaScript('resetView()');
    } else {
      _ac.reset();
      setState(() => _rotation = 0);
    }
  }

  void _selectPart(String id) {
    _selectedPart = id;
    if (_webViewAvailable) {
      _wvc?.runJavaScript('highlightPart("$id")');
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070B10),
      body: SafeArea(
        child: Container(
          margin: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFF1C2C41)),
            borderRadius: BorderRadius.circular(4),
            gradient: const LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xF504080D), Color(0xFA070D14)],
            ),
          ),
          child: Stack(children: [
            // ── 主体：视口 + 面板（面板撑满全高）──
            Row(children: [
              Expanded(flex: 3, child: _buildViewport()),
              SizedBox(
                width: 300,
                child: Container(
                  decoration: const BoxDecoration(
                    border: Border(left: BorderSide(color: Color(0x1F93A4BA))),
                    color: Color(0xD1080D13),
                  ),
                  child: Column(children: [
                    _buildPanelHead(),
                    const Divider(height: 1, color: Color(0x1A93A4BA)),
                    Expanded(child: _buildPanelBody()),
                  ]),
                ),
              ),
            ]),
            // ── 底部栏：仅覆盖视口区域 ──
            Positioned(
              left: 0, right: 300, bottom: 0,
              child: _buildBottomBar(),
            ),
          ]),
        ),
      ),
    );
  }

  Widget _buildViewport() {
    if (_error != null && !_webViewAvailable) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.info_outline, size: 40, color: AppTheme.textSecondary),
        const SizedBox(height: 12),
        const Text('3D 模型预览 (线框模式)', style: AppTheme.bodyValue),
        const SizedBox(height: 4),
        Text(_error!, style: AppTheme.bodyLabel, textAlign: TextAlign.center),
      ]));
    }

    return ClipRRect(
      borderRadius: const BorderRadius.horizontal(left: Radius.circular(3)),
      child: Stack(children: [
        // WebView（移动端）
        if (_webViewAvailable && _wvc != null)
          Positioned.fill(child: WebViewWidget(controller: _wvc!)),

        // 线框回退（Web/Desktop）
        if (!_webViewAvailable)
          Positioned.fill(
            child: AnimatedBuilder(
              animation: _ac,
              builder: (_, __) => CustomPaint(
                size: Size.infinite,
                painter: _WireframePainter(
                  rotation: _autoRotate ? _ac.value * 2 * pi : _rotation,
                  selectedPart: _selectedPart,
                ),
              ),
            ),
          ),

        // 加载中
        if (_loading && !_webViewReady)
          const Positioned.fill(
            child: Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                SizedBox(width: 36, height: 36,
                  child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.accent)),
                SizedBox(height: 12),
                Text('加载 3D 模型…', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ]),
            ),
          ),
      ]),
    );
  }

  Widget _buildPanelHead() {
    final info = _info;
    final hasSelection = info != null || _rawPartName.isNotEmpty;
    final title = info?.name ?? (_rawPartName.isNotEmpty ? _rawPartName : '选择部件');
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      child: Row(children: [
        if (hasSelection)
          GestureDetector(
            onTap: () {
              _wvc?.runJavaScript('clearHighlight()');
              setState(() { _selectedPart = null; _rawPartName = ''; });
            },
            child: Container(
              width: 28, height: 28,
              margin: const EdgeInsets.only(right: 8),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0x2493A4BA)),
              ),
              child: const Icon(Icons.arrow_back_ios_new, size: 14, color: AppTheme.textSecondary),
            ),
          ),
        Expanded(child: Text(title,
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textPrimary),
          overflow: TextOverflow.ellipsis)),
        const SizedBox(width: 8),
        StatusBadge(text: hasSelection ? '已选中' : '点击查看', active: true),
      ]),
    );
  }

  Widget _buildPanelBody() {
    final info = _info;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(14),
      child: info != null
          ? _buildDetail(info)
          : _rawPartName.isNotEmpty
              ? _buildUnknownPart()
              : _buildOverview(),
    );
  }

  Widget _buildOverview() {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      GlassCard(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Column(children: [
          const InfoRow(label: '车型', value: 'Rosmaster X3 Plus'),
          const Divider(color: AppTheme.dividerLine, height: 18),
          const InfoRow(label: '主控', value: 'NVIDIA Jetson Orin Nano'),
          const Divider(color: AppTheme.dividerLine, height: 18),
          const InfoRow(label: '传感器', value: 'LiDAR + 深度相机 + 8×IoT'),
          const Divider(color: AppTheme.dividerLine, height: 18),
          const InfoRow(label: '驱动方式', value: '四轮独立驱动 (麦轮)'),
          const Divider(color: AppTheme.dividerLine, height: 18),
          InfoRow(label: '电池', value: '12.6V 锂电池 · ${widget.carState.batteryPercent}%'),
        ]),
      ),
      const SizedBox(height: 14),
      const Text('部件列表', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
      const SizedBox(height: 10),
      Wrap(spacing: 8, runSpacing: 8, children: _parts.map((p) => _buildPartTag(p)).toList()),
    ]);
  }

  Widget _buildPartTag(_PartInfo p) {
    final active = _selectedPart == p.id;
    return GestureDetector(
      onTap: () => _selectPart(p.id),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          border: Border.all(color: active ? AppTheme.accent : AppTheme.cardBorder),
          borderRadius: BorderRadius.circular(8),
          color: active ? AppTheme.accent.withAlpha(20) : const Color(0x99182537),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          _partIcon(p.id, size: 14, color: active ? AppTheme.accent : AppTheme.textSecondary),
          const SizedBox(width: 6),
          Text(p.name, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700,
            color: active ? AppTheme.accent : AppTheme.textSecondary)),
        ]),
      ),
    );
  }

  Widget _partIcon(String id, {double size = 14, Color? color}) {
    return switch (id) {
      'lidar' => AppIcons.radar(size: size, color: color),
      'camera' => AppIcons.camera(size: size, color: color),
      'light' => AppIcons.lightbulb(size: size, color: color),
      'wheel' => AppIcons.car(size: size, color: color),
      _ => AppIcons.settings(size: size, color: color),
    };
  }

  Widget _buildDetail(_PartInfo info) {
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Column(children: [
        InfoRow(label: '名称', value: info.model),
        const Divider(color: AppTheme.dividerLine, height: 18),
        InfoRow(label: '类型', value: info.type),
        const Divider(color: AppTheme.dividerLine, height: 18),
        ...info.specs.map((s) {
          final parts = s.split(': ');
          return Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: InfoRow(label: parts[0], value: parts.length > 1 ? parts[1] : ''),
          );
        }),
      ]),
    );
  }

  Widget _buildUnknownPart() {
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Column(children: [
        const InfoRow(label: 'Mesh 名称', value: ''),
        Padding(padding: const EdgeInsets.only(top: 8), child: Text(_rawPartName, style: AppTheme.bodyValue)),
        const SizedBox(height: 16),
        const Text('该部件暂未收录详细信息', style: AppTheme.bodyLabel),
      ]),
    );
  }

  Widget _buildBottomBar() {
    return Container(
      height: 44,
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: Color(0x1F93A4BA))),
        color: Color(0xE0070C13),
      ),
      child: Row(children: [
        _bBtn(Icons.arrow_back, '返回主页', () => Navigator.of(context).pop()),
        const SizedBox(width: 8),
        _bBtn(null, '自动旋转', _toggleRotate, icon: AppIcons.rotateCcw(size: 14, color: AppTheme.textPrimary), active: _autoRotate),
        const SizedBox(width: 8),
        _bBtn(null, '重置视角', _resetView, icon: AppIcons.move(size: 14, color: AppTheme.textPrimary)),
      ]),
    );
  }

  Widget _bBtn(IconData? iconData, String label, VoidCallback onTap, {Widget? icon, bool active = false}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10),
        height: 28,
        decoration: BoxDecoration(
          border: Border.all(color: active ? AppTheme.accent : const Color(0x2493A4BA)),
          borderRadius: BorderRadius.circular(8),
          color: active ? AppTheme.accent.withAlpha(20) : const Color(0xB8111A27),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null) ...[icon, const SizedBox(width: 5)],
          if (iconData != null) ...[Icon(iconData, size: 14, color: active ? AppTheme.accent : AppTheme.textPrimary), const SizedBox(width: 5)],
          Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: active ? AppTheme.accent : AppTheme.textSecondary)),
        ]),
      ),
    );
  }

  // ═══ Three.js HTML (仅移动端 WebView 使用) ═══
  String _buildHtml(String modelBase64) {
    return '''
<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<style>
  *{margin:0;padding:0} body{background:#0B121C;overflow:hidden;touch-action:pan-x pan-y pinch-zoom}
  canvas{display:block} #loading{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);color:#8997A8;font-family:sans-serif;font-size:14px}
</style>
</head><body>
<div id="loading">加载模型…</div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const scene=new THREE.Scene(); scene.background=new THREE.Color(0x0B121C);
const camera=new THREE.PerspectiveCamera(45,2,0.05,50); camera.position.set(1.2,0.6,1.2); camera.lookAt(0,0,0);
const renderer=new THREE.WebGLRenderer({antialias:true}); renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
renderer.shadowMap.enabled=true; renderer.shadowMap.type=THREE.PCFSoftShadowMap; document.body.appendChild(renderer.domElement);
scene.add(new THREE.AmbientLight(0x8899bb,1.4));
const sun=new THREE.DirectionalLight(0xffffff,2.5); sun.position.set(5,8,3); sun.castShadow=true;
sun.shadow.mapSize.set(1024,1024); sun.shadow.camera.near=0.5; sun.shadow.camera.far=30;
sun.shadow.camera.left=-5; sun.shadow.camera.right=5; sun.shadow.camera.top=5; sun.shadow.camera.bottom=-5; scene.add(sun);
const fill=new THREE.DirectionalLight(0x8899cc,0.6); fill.position.set(-2,1,-2); scene.add(fill);
const grid=new THREE.GridHelper(3,20,0x5BAEC7,0x1A3040); grid.position.y=-1.2; scene.add(grid);
const ringGeo=new THREE.TorusGeometry(0.52,0.008,16,80);
const ring=new THREE.Mesh(ringGeo,new THREE.MeshBasicMaterial({color:0x5BAEC7,transparent:true,opacity:0.25}));
ring.rotation.x=Math.PI/2; ring.position.y=-0.95; ring.name='ring'; scene.add(ring);
const controls=new OrbitControls(camera,renderer.domElement); controls.target.set(0,0,0);
controls.enableDamping=true; controls.dampingFactor=0.08; controls.minDistance=0.5; controls.maxDistance=3;
controls.maxPolarAngle=Math.PI*0.65; controls.autoRotate=false; controls.autoRotateSpeed=0.6; controls.update();
const loader=new GLTFLoader();
const blob=Uint8Array.from(atob('$modelBase64'),c=>c.charCodeAt(0));
const url=URL.createObjectURL(new Blob([blob],{type:'application/octet-stream'})); let model;
loader.load(url,gltf=>{model=gltf.scene;_names=[];model.traverse(n=>{if(n.isMesh){n.castShadow=true;n.receiveShadow=true;if(n.name)_names.push(n.name)}});scene.add(model);document.getElementById('loading').style.display='none';modelLoaded.postMessage('ok|'+JSON.stringify(_names));URL.revokeObjectURL(url)});
const raycaster=new THREE.Raycaster();
let _hl=[],_names=[];renderer.domElement.addEventListener('click',e=>{if(!model)return;const rect=renderer.domElement.getBoundingClientRect();const mouse=new THREE.Vector2(((e.clientX-rect.left)/rect.width)*2-1,-((e.clientY-rect.top)/rect.height)*2+1);raycaster.setFromCamera(mouse,camera);const hits=raycaster.intersectObjects(model.children,true);if(hits.length>0){let obj=hits[0].object;while(obj&&obj!==model){if(obj.name&&obj.name.length>0){partSelected.postMessage(obj.name);return}obj=obj.parent}}});window.toggleAutoRotate=v=>{controls.autoRotate=v};window.resetView=()=>{camera.position.set(1.2,0.6,1.2);controls.target.set(0,0,0);controls.update()};window.highlightPart=name=>{if(!model)return;clearHighlight();const lower=name.toLowerCase();const out=[];model.traverse(n=>{if(!n.isMesh||!n.name)return;const nl=n.name.toLowerCase();if(nl.includes(lower))out.push(n);if(lower==='lidar'&&nl.includes('laser_link'))out.push(n);if(lower==='light'&&(nl.includes('cylinder003')||nl.includes('cylinder009')||nl.includes('silver_rim')))out.push(n);if(lower==='wheel'&&(nl.includes('wheel')||nl.includes('左')||nl.includes('右')))out.push(n)});out.forEach(n=>{n.material.emissive=new THREE.Color(0xe88b45);n.material.emissiveIntensity=0.6});_hl=out};window.clearHighlight=()=>{_hl.forEach(n=>{n.material.emissive.set(0x000000);n.material.emissiveIntensity=0});_hl=[]};
function resize(){const w=window.innerWidth,h=window.innerHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix()}
window.addEventListener('resize',resize);resize();
function animate(){requestAnimationFrame(animate);controls.update();ring.rotation.z+=0.002;renderer.render(scene,camera)}animate();
</script></body></html>''';
  }
}

/// ═══ 线框回退 (Web/Desktop 无 WebView 时使用) ═══
class _WireframePainter extends CustomPainter {
  final double rotation;
  final String? selectedPart;
  _WireframePainter({required this.rotation, required this.selectedPart});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2, cy = size.height / 2;

    // 网格地板
    final fp = Paint()
      ..shader = RadialGradient(
        center: const Alignment(0, 0.3),
        colors: [const Color(0x245BAEC7), const Color(0x005BAEC7)],
      ).createShader(Rect.fromCircle(center: Offset(cx, cy + size.height * 0.32), radius: size.width * 0.4));
    canvas.drawOval(Rect.fromCenter(center: Offset(cx, cy + size.height * 0.32), width: size.width * 0.75, height: size.width * 0.14), fp);

    // 旋转环
    canvas.save(); canvas.translate(cx, cy); canvas.rotate(rotation);
    canvas.drawOval(Rect.fromCircle(center: Offset.zero, radius: 90),
      Paint()..style = PaintingStyle.stroke..strokeWidth = 1..color = const Color(0x485BAEC7));
    canvas.drawOval(Rect.fromCircle(center: Offset.zero, radius: 98),
      Paint()..style = PaintingStyle.stroke..strokeWidth = 1..color = const Color(0x24E88B45));
    canvas.restore();

    // 小车线框
    canvas.save(); canvas.translate(cx, cy);
    canvas.scale(1.0);

    final body = RRect.fromLTRBR(-76, -47, 76, 47, const Radius.circular(14));
    canvas.drawRRect(body, Paint()..style = PaintingStyle.stroke..strokeWidth = 2..color = const Color(0x595BAEC7));
    canvas.drawRRect(body, Paint()..color = const Color(0x6118283A));

    // LiDAR 塔
    canvas.drawRRect(RRect.fromLTRBR(-18, -65, 18, -47, const Radius.circular(6)), Paint()..color = const Color(0x521A2432));
    canvas.drawRRect(RRect.fromLTRBR(-18, -65, 18, -47, const Radius.circular(6)),
      Paint()..style = PaintingStyle.stroke..strokeWidth = 2..color = selectedPart == 'lidar' ? AppTheme.accent : const Color(0x4D5BAEC7));

    // 中部
    canvas.drawRRect(RRect.fromLTRBR(-26, -10, 26, 18, const Radius.circular(4)), Paint()..color = const Color(0x4D1A2431));
    canvas.drawRect(RRect.fromLTRBR(-26, -10, 26, 18, const Radius.circular(4)).outerRect,
      Paint()..style = PaintingStyle.stroke..strokeWidth = 1..color = const Color(0x29E88B45));

    // 轮子
    final wp = Paint()..style = PaintingStyle.stroke..strokeWidth = 2..color = selectedPart == 'wheel' ? AppTheme.accent : const Color(0x6B93A4BA);
    final wf = Paint()..color = const Color(0x9E141E2A);
    final off = 0.0;
    _w(canvas, -76 + off, -24 + off, wf, wp); _w(canvas, 54 + off, -24 - off, wf, wp);
    _w(canvas, -76 + off, 30 - off, wf, wp); _w(canvas, 54 - off, 30 + off, wf, wp);
    canvas.restore();
  }

  void _w(Canvas c, double x, double y, Paint f, Paint s) {
    c.drawRRect(RRect.fromLTRBR(x, y, x + 18, y + 26, const Radius.circular(5)), f);
    c.drawRRect(RRect.fromLTRBR(x, y, x + 18, y + 26, const Radius.circular(5)), s);
  }

  @override
  bool shouldRepaint(covariant _WireframePainter o) =>
      rotation != o.rotation || selectedPart != o.selectedPart;
}

class _PartInfo {
  final String id, name, model, type;
  final List<String> specs;
  const _PartInfo(this.id, this.name, this.model, this.type, this.specs);
}
