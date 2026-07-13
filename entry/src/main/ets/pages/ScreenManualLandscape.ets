/**
 * 横屏手动接管页面
 * 参照 manual-landscape.html 原型，使用 SVG 图标。
 * 全屏横屏布局：双摇杆 + 视频 + 雷达 + 工具列 + 急停控制。
 */
import promptAction from '@ohos.promptAction'
import router from '@ohos.router'
import { ScreenUtils } from '../utils/ScreenUtils'
import { FG } from '../fireguard/Theme'
import { CarRockerComponents } from '../components/CarRockerComponents'
import { ViewRockerComponents } from '../components/ViewRockerComponents'
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
      // 背景层
      Column()
        .width('100%')
        .height('100%')
        .backgroundColor('#0a1622')

      // 视频画面（底层背景）
      Web({ src: this.getVideoUrl(), controller: this.webCtl })
        .width('100%')
        .height('100%')
        .opacity(0.85)

      // 雷达小窗
      this.radarWidget()

      // 底部道路条
      Row()
        .width('100%')
        .height(1)
        .backgroundColor('rgba(255, 255, 255, 0.06)')
        .position({ x: 0, y: '85%' })

      // ===== 左上：状态栏 =====
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
            .backgroundColor('#2dcf9f')
            .margin({ right: 4 })
          Text(`接管中 | ${this.signalText}%`)
            .fontSize(FG.smallSize)
            .fontColor('#2dcf9f')
        }
        .margin({ top: 4 })
      }
      .width(180)
      .padding({ left: 14, right: 14, top: 10, bottom: 10 })
      .borderRadius(12)
      .border({ width: 1, color: 'rgba(147, 164, 186, 0.14)' })
      .backgroundColor('rgba(5, 8, 13, 0.82)')
      .position({ x: 16, y: 12 })

      // ===== 右上：FPS 面板 =====
      Row() {
        // 设置图标
        Image($r('app.media.settings'))
          .width(24)
          .height(24)
          .fillColor(FG.text)
          .onClick(() => {
            promptAction.showToast({ message: '布局设置（待后端接入）' })
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
      .position({ x: '88%', y: 12 })

      // ===== 右侧工具列 =====
      Column({ space: 8 }) {
        this.toolIconBtn($r('app.media.lightbulb'), '灯')
        this.toolIconBtn($r('app.media.mic'), '麦')
        this.toolIconBtn($r('app.media.record'), '录')
        this.toolIconBtn($r('app.media.radar'), '雷')
        this.toolIconBtn($r('app.media.map'), '图')
      }
      .position({ x: '94%', y: 56 })

      // ===== 左下：运动摇杆 (120x120) =====
      Row() {
        CarRockerComponents()
      }
      .width(120)
      .height(120)
      .position({ x: 20, y: '68%' })

      // ===== 右下：视角摇杆 (140x62) =====
      Row() {
        ViewRockerComponents()
      }
      .width(140)
      .height(62)
      .position({ x: '74%', y: '78%' })

      // ===== 底部居中：后退 + 急停 + 速度 =====
      Row() {
        // 后退按钮（圆形）
        Row() {
          Image($r('app.media.arrow-left'))
            .width(18)
            .height(18)
            .fillColor(FG.muted)
        }
        .width(44)
        .height(36)
        .borderRadius(10)
        .border({ width: 1, color: 'rgba(147, 164, 186, 0.14)' })
        .backgroundColor('rgba(17, 26, 39, 0.72)')
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          router.back()
        })
        .margin({ right: 12 })

        // 急停按钮
        Row() {
          Image($r('app.media.octagon-alert'))
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
        .margin({ right: 12 })

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
      .position({ x: '50%', y: '92%' })
      .translate({ x: '-50%', y: 0 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#0a1622')
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
    .position({ x: 240, y: 120 })
  }

  private getVideoUrl(): string {
    if (BackendState.type === BackendType.REST) {
      return `http://${BackendState.ip}:5000/video_feed`
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
