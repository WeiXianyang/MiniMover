/**
 * 小车 3D 车模页面（路由页）
 * 用 Web + three.js 加载本地 rawfile/model3d/car.glb，点击部件高亮并显示详情。
 * 参照 model/3d-model-deployment-guide.md 的部件映射（原文档为 Flutter，本页移植到 ArkTS）。
 */
import router from '@ohos.router'
import web_webview from '@ohos.web.webview'
import { ScreenUtils } from '../utils/ScreenUtils'
import { FG } from '../fireguard/Theme'
import { FgPageHead, FgStatus } from '../fireguard/Widgets'
import { restApiClient } from '../tcp/RestApiClient'
import { CarStatus } from '../tcp/CarModels'

/** 部件信息 */
interface PartInfo {
  id: string
  name: string
  model: string
  desc: string
  specs: string[]
}

@Entry
@Component
struct ScreenModel3D {
  private controller: web_webview.WebviewController = new web_webview.WebviewController()
  /** 当前选中部件 id，空表示概览 */
  @State selected: string = ''
  /** 自动旋转开关 */
  @State autoRotate: boolean = true
  /** 模型加载失败 */
  @State loadError: boolean = false
  /** 实时遥测（接入现有 /api/status），null 为未取到 */
  @State telemetry: CarStatus | null = null
  private pollTimer: number = -1

  /** 四个部件详情，取自部署文档 _parts */
  private parts: PartInfo[] = [
    { id: 'lidar', name: '激光雷达', model: 'RPLIDAR A1', desc: '360° 激光扫描测距',
      specs: ['范围: 0.15m – 12m', '频率: 8000 次/秒', '状态: ● 正常'] },
    { id: 'camera', name: '深度相机', model: 'Astra Pro Plus', desc: '深度 + RGB 双目',
      specs: ['分辨率: 1280×720 @30fps', '深度: 0.6m – 8m', '状态: ● 正常'] },
    { id: 'light', name: '车前灯', model: 'LED 矩阵大灯', desc: '可编程 RGB 灯组',
      specs: ['亮度: 0 – 100% 可调', '模式: 常亮 · 闪烁 · 呼吸', '状态: ● 正常'] },
    { id: 'wheel', name: '驱动轮组', model: '麦克纳姆轮组 ×4', desc: '独立悬挂 · 全向移动',
      specs: ['电机: 编码器减速 ×4', '转速: 160 RPM', '状态: ● 正常'] }
  ]

  aboutToAppear(): void {
    const ctx = getContext(this)
    ScreenUtils.setLandscape(ctx)
    this.refreshTelemetry()
    this.pollTimer = setInterval(() => { this.refreshTelemetry() }, 3000)
  }

  aboutToDisappear(): void {
    const ctx = getContext(this)
    ScreenUtils.setPortrait(ctx)
    if (this.pollTimer !== -1) {
      clearInterval(this.pollTimer)
      this.pollTimer = -1
    }
  }

  onBackPress(): boolean {
    return true
  }

  private async refreshTelemetry(): Promise<void> {
    const status: CarStatus | null = await restApiClient.getStatus()
    if (status !== null) {
      this.telemetry = status
    }
  }

  /** JS→ArkTS 桥：three.js 点中部件时回调 */
  private onPartSelected(id: string): void {
    this.selected = id
    this.autoRotate = false
  }

  private currentPart(): PartInfo | null {
    for (let i = 0; i < this.parts.length; i++) {
      if (this.parts[i].id === this.selected) {
        return this.parts[i]
      }
    }
    return null
  }

  build() {
    Column() {
      // 顶部返回
      Row() {
        Image($r('app.media.arrow_left'))
          .width(18)
          .height(18)
          .fillColor(FG.text)
        Text('返回')
          .fontSize(FG.bodySize)
          .fontColor(FG.text)
          .margin({ left: 4 })
      }
      .height(32)
      .alignSelf(ItemAlign.Start)
      .margin({ bottom: 12 })
      .onClick(() => { router.back() })

      FgPageHead({
        title: '3D 车模',
        subtitle: '点击部件查看详情',
        pillText: this.loadError ? '加载失败' : '交互模型',
        pillStatus: this.loadError ? FgStatus.Red : FgStatus.Green
      })

      // 3D 视图
      Stack() {
        Web({ src: $rawfile('model3d/viewer.html'), controller: this.controller })
          .width('100%')
          .height('100%')
          .backgroundColor('#0a1622')
          .javaScriptAccess(true)
          .domStorageAccess(true)
          .javaScriptProxy({
            object: {
              onPart: (id: string): void => { this.onPartSelected(id) },
              onMeshNames: (json: string): void => { console.log('[Model3D] mesh names: ' + json) },
              onLoadError: (msg: string): void => { this.loadError = true; console.error('[Model3D] load error: ' + msg) }
            },
            name: 'model3d',
            methodList: ['onPart', 'onMeshNames', 'onLoadError'],
            controller: this.controller
          })

        if (this.loadError) {
          Text('3D 模型加载失败\n请确认 car.glb 已打包进 rawfile')
            .fontSize(FG.bodySize)
            .fontColor(FG.muted)
            .textAlign(TextAlign.Center)
        }
      }
      .width('100%')
      .layoutWeight(1)
      .borderRadius(FG.cardRadius)
      .clip(true)
      .backgroundColor('#0a1622')
      .border({ width: 1, color: FG.line })
      .margin({ bottom: 12 })

      // 详情 / 概览面板
      if (this.currentPart() !== null) {
        this.partDetail(this.currentPart()!)
      } else {
        this.overviewHint()
      }

      // 底部控制
      Row() {
        Row() {
          Text(this.autoRotate ? '暂停旋转' : '自动旋转')
            .fontSize(FG.bodySize)
            .fontWeight(FontWeight.Bold)
            .fontColor(FG.text)
        }
        .layoutWeight(1)
        .height(46)
        .justifyContent(FlexAlign.Center)
        .borderRadius(FG.btnRadius)
        .backgroundColor(FG.btnDefault)
        .margin({ right: 5 })
        .onClick(() => { this.toggleRotate() })

        Row() {
          Image($r('app.media.rotate_ccw'))
            .width(18)
            .height(18)
            .fillColor('#10151d')
          Text('重置视角')
            .fontSize(FG.bodySize)
            .fontWeight(FontWeight.Bold)
            .fontColor('#10151d')
            .margin({ left: 6 })
        }
        .layoutWeight(1)
        .height(46)
        .justifyContent(FlexAlign.Center)
        .borderRadius(FG.btnRadius)
        .backgroundColor(FG.orange)
        .margin({ left: 5 })
        .onClick(() => { this.resetView() })
      }
      .width('100%')
      .margin({ top: 12 })
    }
    .width('100%')
    .height('100%')
    .padding(20)
    .backgroundColor(FG.bg)
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  partDetail(p: PartInfo) {
    Column() {
      Row() {
        Column() {
          Text(p.name)
            .fontSize(FG.recommendSize)
            .fontWeight(FontWeight.Bold)
            .fontColor(FG.orange)
          Text(p.model)
            .fontSize(FG.labelSize)
            .fontColor(FG.muted)
            .margin({ top: 4 })
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1)

        Text('取消高亮')
          .fontSize(FG.smallSize)
          .fontColor(FG.muted)
          .padding({ left: 10, right: 10, top: 6, bottom: 6 })
          .borderRadius(FG.pillRadius)
          .backgroundColor(FG.btnDefault)
          .onClick(() => { this.clearSelection() })
      }
      .width('100%')

      Text(p.desc)
        .fontSize(FG.bodySize)
        .fontColor(FG.text)
        .margin({ top: 10, bottom: 8 })

      ForEach(p.specs, (s: string) => {
        Text(s)
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .margin({ top: 4 })
      }, (s: string) => s)

      if (this.telemetry !== null) {
        // 连接后展示实时遥测，按部件展示对应数据
        this.telemetryRow(p)
      } else {
        Text('未连接设备，实时数据不可用')
          .fontSize(FG.smallSize).fontColor('rgba(147,164,186,0.4)').margin({ top: 10 })
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
    .padding(15)
    .borderRadius(FG.cardRadius)
    .border({ width: 1, color: 'rgba(255, 151, 72, 0.42)' })
    .linearGradient({
      angle: 135,
      colors: [['rgba(255, 151, 72, 0.17)', 0], [FG.cardBg, 1]]
    })
  }

  @Builder
  telemetryRow(p: PartInfo) {
    Row()
      .width('100%')
      .height(1)
      .backgroundColor('rgba(255, 151, 72, 0.2)')
      .margin({ top: 10, bottom: 8 })

    Text('设备状态（实时）')
      .fontSize(FG.smallSize)
      .fontColor(FG.orange)
      .margin({ bottom: 6 })

    if (p.id === 'lidar') {
      Text(`气压: ${this.telemetry!.sensors.pressure.toFixed(1)} hPa`)
        .fontSize(FG.labelSize).fontColor(FG.muted).margin({ top: 3 })
      Text(`光照: ${this.telemetry!.sensors.light} lux`)
        .fontSize(FG.labelSize).fontColor(FG.muted).margin({ top: 3 })
    } else if (p.id === 'camera') {
      Text(`温度: ${this.telemetry!.sensors.temperature.toFixed(1)}°C`)
        .fontSize(FG.labelSize).fontColor(FG.muted).margin({ top: 3 })
      Text(`湿度: ${this.telemetry!.sensors.humidity.toFixed(1)}%`)
        .fontSize(FG.labelSize).fontColor(FG.muted).margin({ top: 3 })
    } else if (p.id === 'wheel') {
      Text(`电量: ${this.telemetry!.battery.toFixed(1)}V`)
        .fontSize(FG.labelSize).fontColor(FG.muted).margin({ top: 3 })
      Text(`IP: ${this.telemetry!.ip}`)
        .fontSize(FG.labelSize).fontColor(FG.muted).margin({ top: 3 })
    } else if (p.id === 'light') {
      Text(`烟雾: ${this.telemetry!.sensors.smoke > 0 ? `${this.telemetry!.sensors.smoke}` : '正常'}`)
        .fontSize(FG.labelSize).fontColor(FG.muted).margin({ top: 3 })
      Text(`CO2: ${this.telemetry!.sensors.co2} ppm`)
        .fontSize(FG.labelSize).fontColor(FG.muted).margin({ top: 3 })
    }
  }

  @Builder
  overviewHint() {
    Column() {
      Text('整车概览')
        .fontSize(FG.recommendSize)
        .fontWeight(FontWeight.Bold)
        .fontColor(FG.text)
      Text('点击模型上的激光雷达、深度相机、车前灯或轮组，查看对应部件规格。')
        .fontSize(FG.labelSize)
        .fontColor(FG.muted)
        .lineHeight(FG.labelSize * 1.55)
        .margin({ top: 9 })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
    .padding(15)
    .borderRadius(FG.cardRadius)
    .border({ width: 1, color: FG.line })
    .backgroundColor(FG.cardBg)
  }

  private toggleRotate(): void {
    this.autoRotate = !this.autoRotate
    this.controller.runJavaScript(`setAutoRotate(${this.autoRotate})`)
  }

  private resetView(): void {
    this.selected = ''
    this.autoRotate = true
    this.controller.runJavaScript('resetView()')
  }

  private clearSelection(): void {
    this.selected = ''
    this.controller.runJavaScript('clearHighlight()')
  }
}
