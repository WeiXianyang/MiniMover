/**
 * 横屏手动接管页面
 * 参照 manual-landscape.html 原型，使用 SVG 图标和手动摇杆组件。
 * 全屏横屏布局：双摇杆 + 视频 + 雷达 + 工具列 + 急停控制。
 * 未连接设备时显示深灰背景占位，确保所有控件清晰可见。
 */
import promptAction from '@ohos.promptAction'
import router from '@ohos.router'
import { ScreenUtils } from '../utils/ScreenUtils'
import { FG } from '../fireguard/Theme'
import { ManualMoveJoystick, ManualViewJoystick } from '../components/ManualJoystickComponents'
import { BackendState, BackendType } from '../CarUtill/BackendType'
import { carApi } from '../CarUtill/CarApi'
import { CarDirection } from '../CarUtill/CarEnum'
import web_webview from '@ohos.web.webview'

@Entry
@Component
struct ScreenManualLandscape {
  @State fpsText: string = '30'
  @State speedText: string = '50'
  @State signalText: string = '86'
  /** 雷达开关状态 */
  @State showRadar: boolean = true
  /** 实际屏幕尺寸（vp），用于自适应定位，默认给一个横屏兜底值 */
  @State stageW: number = 780
  @State stageH: number = 360
  private webCtl: web_webview.WebviewController = new web_webview.WebviewController()

  aboutToAppear(): void {
    const ctx = getContext(this)
    ScreenUtils.setLandscape(ctx)
  }

  aboutToDisappear(): void {
    const ctx = getContext(this)
    ScreenUtils.setPortrait(ctx)
  }

  onBackPress(): boolean {
    return true
  }

  build() {
    Stack() {
      // 背景层：始终为深色
      Column() {
        // 未连接小车的提示占位
        if (!BackendState.connected) {
          Column() {
            Row()
              .width(80)
              .height(80)
              .borderRadius(40)
              .border({ width: 2, color: 'rgba(147, 164, 186, 0.3)', style: BorderStyle.Dashed })
              .margin({ bottom: 16 })
              .justifyContent(FlexAlign.Center)
            Text('未连接设备')
              .fontSize(18)
              .fontWeight(FontWeight.Bold)
              .fontColor(FG.text)
              .margin({ bottom: 8 })
            Text('请先在"连接"页面连接小车后进入手动接管')
              .fontSize(FG.bodySize)
              .fontColor(FG.muted)
          }
          .width('100%')
          .layoutWeight(1)
          .justifyContent(FlexAlign.Center)
          .alignItems(HorizontalAlign.Center)
        }
      }
      .width('100%')
      .height('100%')
      .backgroundColor('#0c1826')

      // 视频画面：仅连接设备后显示
      if (BackendState.connected) {
        Web({ src: this.getVideoUrl(), controller: this.webCtl })
          .width('100%')
          .height('100%')
      }

      // 雷达小窗（可开关）
      if (this.showRadar) {
        this.radarWidget()
      }

      // 底部道路条
      Row()
        .width('100%')
        .height(1)
        .backgroundColor('rgba(255, 255, 255, 0.06)')
        .position({ x: 0, y: '85%' })

      // ===== 左上：返回按钮 =====
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
      .padding({ left: 10, right: 14 })
      .borderRadius(10)
      .border({ width: 1, color: 'rgba(147, 164, 186, 0.22)' })
      .backgroundColor('rgba(28, 37, 50, 0.9)')
      .position({ x: 16, y: 12 })
      .onClick(() => {
        router.back()
      })

      // ===== 左上：状态栏（返回按钮下方） =====
      Column() {
        Text('手动接管')
          .fontSize(16)
          .fontWeight(FontWeight.Bold)
          .fontColor(FG.text)
        Row() {
          Row()
            .width(6)
            .height(6)
            .borderRadius(3)
            .backgroundColor(BackendState.connected ? '#2dcf9f' : FG.red)
            .margin({ right: 4 })
          Text(BackendState.connected ? `接管中 | ${this.signalText}%` : '未连接')
            .fontSize(FG.smallSize)
            .fontColor(BackendState.connected ? '#2dcf9f' : FG.red)
        }
        .margin({ top: 4 })
      }
      .width(180)
      .padding({ left: 14, right: 14, top: 10, bottom: 10 })
      .borderRadius(12)
      .border({ width: 1, color: 'rgba(147, 164, 186, 0.14)' })
      .backgroundColor('rgba(5, 8, 13, 0.82)')
      .position({ x: 16, y: 52 })

      // ===== 右上：FPS 面板 =====
      Row() {
        Image($r('app.media.settings'))
          .width(24)
          .height(24)
          .fillColor(FG.text)
          .onClick(() => {
            router.pushUrl({ url: 'pages/ScreenManualSettings' })
          })

        Text(`${this.fpsText} FPS`)
          .fontSize(13)
          .fontWeight(FontWeight.Bold)
          .fontColor('#2dcf9f')

        Text('|')
          .fontSize(13)
          .fontColor(FG.muted)

        Text('●●●●○')
          .fontSize(10)
          .fontColor(FG.muted)
      }
      .height(28)
      .padding({ left: 14, right: 14 })
      .borderRadius(10)
      .border({ width: 1, color: 'rgba(147, 164, 186, 0.12)' })
      .backgroundColor('rgba(5, 8, 13, 0.82)')
      .position({ x: this.stageW - 148, y: 12 })

      // ===== 右侧工具列 =====
      Column({ space: 8 }) {
        this.toolIconBtn($r('app.media.lightbulb'), '灯')
        this.toolIconBtn($r('app.media.mic'), '麦')
        this.toolIconBtn($r('app.media.record'), '录')
        this.toolIconBtn($r('app.media.radar'), '雷')
        // 第五个：雷达开关
        Row() {
          Image($r('app.media.map'))
            .width(18)
            .height(18)
            .fillColor(this.showRadar ? FG.orange : FG.muted)
        }
        .width(44)
        .height(42)
        .borderRadius(10)
        .border({
          width: 1,
          color: this.showRadar ? 'rgba(232, 139, 69, 0.28)' : 'rgba(147, 164, 186, 0.16)'
        })
        .backgroundColor('rgba(28, 37, 50, 0.86)')
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          this.showRadar = !this.showRadar
        })
      }
      .position({ x: this.stageW - 44 - 12, y: 56 })

      // ===== 左下：运动摇杆 (120x120)，从底边反向锚定，避免溢出 =====
      ManualMoveJoystick()
        .width(120)
        .height(120)
        .position({ x: 20, y: this.stageH - 120 - 14 })

      // ===== 右下：视角摇杆 (140x62)，从右下角反向锚定 =====
      ManualViewJoystick()
        .width(140)
        .height(62)
        .position({ x: this.stageW - 140 - 16, y: this.stageH - 62 - 60 })

      // ===== 底部居中：急停 + 速度 =====
      Row() {
        // 急停按钮
        Row() {
          Image($r('app.media.octagon_alert'))
            .width(18)
            .height(18)
            .fillColor('#ff5f66')
          Text('急停')
            .fontSize(14)
            .fontWeight(FontWeight.Bold)
            .fontColor('#ff5f66')
        }
        .width(116)
        .height(42)
        .borderRadius(FG.pillRadius)
        .border({ width: 1, color: 'rgba(255, 101, 112, 0.34)' })
        .backgroundColor('rgba(93, 23, 30, 0.58)')
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          this.emergencyStop()
        })
        .margin({ right: 16 })

        // 速度显示
        Row() {
          Text('速度 ')
            .fontSize(12)
            .fontColor(FG.muted)
          Text(`${this.speedText}%`)
            .fontSize(12)
            .fontWeight(FontWeight.Bold)
            .fontColor(FG.orange)
        }
        .height(36)
        .padding({ left: 12, right: 12 })
        .borderRadius(10)
        .border({ width: 1, color: 'rgba(147, 164, 186, 0.14)' })
        .backgroundColor('rgba(17, 26, 39, 0.72)')
      }
      .position({ x: '50%', y: this.stageH - 42 - 12 })
      .translate({ x: '-50%', y: 0 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#0c1826')
    .onAreaChange((_o: Area, n: Area) => {
      this.stageW = new Number(n.width).valueOf()
      this.stageH = new Number(n.height).valueOf()
    })
  }

  @Builder
  toolIconBtn(icon: Resource, label: string) {
    Row() {
      Image(icon)
        .width(18)
        .height(18)
        .fillColor(FG.muted)
    }
    .width(44)
    .height(42)
    .borderRadius(10)
    .border({ width: 1, color: 'rgba(147, 164, 186, 0.16)' })
    .backgroundColor('rgba(28, 37, 50, 0.86)')
    .justifyContent(FlexAlign.Center)
    .onClick(() => {
      promptAction.showToast({ message: `${label}（待后端接入）` })
    })
  }

  @Builder
  radarWidget() {
    Stack() {
      // 雷达图标居中
      Image($r('app.media.radar'))
        .width(22)
        .height(22)
        .fillColor(FG.cyan)

      // 外圈
      Circle()
        .width(140)
        .height(140)
        .fill(Color.Transparent)
        .stroke('rgba(147, 164, 186, 0.18)').strokeWidth(1)

      // 内圈（inset 22px → 96x96）
      Circle()
        .width(96)
        .height(96)
        .fill(Color.Transparent)
        .stroke('rgba(147, 164, 186, 0.12)').strokeWidth(1)

      // 扫描线（从中心，-32° 旋转）
      Line()
        .width(54)
        .height(1)
        .stroke('rgba(48, 211, 255, 0.5)').strokeWidth(1)
        .rotate({ angle: -32 })

      // 检测点
      Circle()
        .width(7)
        .height(7)
        .fill(FG.orange)
        .position({ x: 98, y: 45 })
    }
    .width(140)
    .height(140)
    .borderRadius(FG.pillRadius)
    .border({ width: 1, color: 'rgba(147, 164, 186, 0.18)' })
    .radialGradient({
      center: ['50%', '50%'],
      radius: 70,
      colors: [['rgba(91, 174, 199, 0.12)', 0], [Color.Transparent, 1]]
    })
    .backgroundColor('rgba(19, 28, 40, 0.48)')
    .position({ x: (this.stageW - 140) / 2, y: Math.max(56, (this.stageH - 140) / 2 - 20) })
  }

  private getVideoUrl(): string {
    if (BackendState.type === BackendType.REST) {
      return `http://${BackendState.ip}:${BackendState.restPort}/video_feed`
    } else {
      return `http://${BackendState.ip}:${BackendState.videoPort}/video_feed`
    }
  }

  private emergencyStop(): void {
    if (BackendState.type === BackendType.REST) {
      carApi.sendRestStop()
      promptAction.showToast({ message: 'REST 急停已发送' })
    } else {
      carApi.carBtnCtrl(CarDirection.Brake)
      promptAction.showToast({ message: 'TCP 急停已发送' })
    }
  }
}
