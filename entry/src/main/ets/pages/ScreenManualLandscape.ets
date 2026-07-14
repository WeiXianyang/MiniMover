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
import { restApiClient } from '../tcp/RestApiClient'
import { ManualLayout } from '../CarUtill/ManualLayout'
import web_webview from '@ohos.web.webview'

@Entry
@Component
struct ScreenManualLandscape {
  @State fpsText: string = '30'
  @State speedText: string = '50'
  @State signalText: string = '86'
  /** 雷达开关状态 */
  @State showRadar: boolean = true
  /** 语音录音状态 */
  @State recording: boolean = false
  /** TTS 喊话输入面板显隐 */
  @State showTts: boolean = false
  /** TTS 待发送文本 */
  @State ttsText: string = ''
  /** 实际屏幕尺寸（vp），用于自适应定位，默认给一个横屏兜底值 */
  @State stageW: number = 780
  @State stageH: number = 360
  private webCtl: web_webview.WebviewController = new web_webview.WebviewController()

  aboutToAppear(): void {
    const ctx = getContext(this)
    ScreenUtils.setLandscape(ctx)
  }

  onPageShow(): void {
    // 从布局设置页返回时本页实例仍存活，不会再触发 aboutToAppear，
    // 故在此重新置横屏，修复"设置保存后变竖屏"的 bug。
    const ctx = getContext(this)
    ScreenUtils.setLandscape(ctx)
  }

  aboutToDisappear(): void {
    // 仅在真正离开手动接管流程（返回竖屏标签页）时恢复竖屏
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

      // ===== 右侧工具列：灯光 / 语音 / 拍照 / 雷达 / 地图 =====
      Column({ space: 8 }) {
        // 灯光：TCP 6000 RGB 灯带（30/31/32），5000 无此接口 → 占位
        this.toolIconBtn($r('app.media.lightbulb'), '灯光（需 TCP 通道）', false)
        // 语音：5000 /api/audio 录音开关
        this.voiceBtn()
        // 拍照：TCP 6000 拍照（60），5000 无此接口 → 占位
        this.toolIconBtn($r('app.media.record'), '拍照（需 TCP 通道）', false)
        // 雷达：本地开关（雷达小窗显隐）
        this.radarToggleBtn()
        // 地图：跳转地图导航页
        this.mapBtn()
      }
      .position({ x: this.stageW - 44 - 12, y: 56 })

      // ===== 运动摇杆 (120x120)：自定义布局优先，否则从底边锚定 =====
      ManualMoveJoystick()
        .width(120)
        .height(120)
        .position(this.movePos())

      // ===== 视角摇杆 (140x62)：自定义布局优先，否则右下角锚定 =====
      ManualViewJoystick()
        .width(140)
        .height(62)
        .position(this.viewPos())

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

      // TTS 喊话浮层（最上层）
      if (this.showTts) {
        this.ttsPanel()
      }
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
  toolIconBtn(icon: Resource, label: string, enabled: boolean) {
    Row() {
      Image(icon)
        .width(18)
        .height(18)
        .fillColor(enabled ? FG.muted : 'rgba(147, 164, 186, 0.4)')
    }
    .width(44)
    .height(42)
    .borderRadius(10)
    .border({ width: 1, color: 'rgba(147, 164, 186, 0.16)' })
    .backgroundColor('rgba(28, 37, 50, 0.86)')
    .justifyContent(FlexAlign.Center)
    .onClick(() => {
      promptAction.showToast({ message: label })
    })
  }

  /** 语音：单击喊话(TTS)，长按录音开关，均接 5000 /api/audio */
  @Builder
  voiceBtn() {
    Row() {
      Image($r('app.media.mic'))
        .width(18)
        .height(18)
        .fillColor(this.recording ? FG.red : FG.muted)
    }
    .width(44)
    .height(42)
    .borderRadius(10)
    .border({
      width: 1,
      color: this.recording ? 'rgba(255, 101, 112, 0.5)' : 'rgba(147, 164, 186, 0.16)'
    })
    .backgroundColor('rgba(28, 37, 50, 0.86)')
    .justifyContent(FlexAlign.Center)
    .gesture(
      GestureGroup(GestureMode.Exclusive,
        LongPressGesture({ repeat: false })
          .onAction(() => { this.toggleRecording() }),
        TapGesture()
          .onAction(() => { this.showTts = true })
      )
    )
  }

  /** TTS 喊话输入面板（居中浮层） */
  @Builder
  ttsPanel() {
    Column() {
      Column() {
        Text('车端喊话')
          .fontSize(16)
          .fontWeight(FontWeight.Bold)
          .fontColor(FG.text)
          .margin({ bottom: 12 })

        TextInput({ text: this.ttsText, placeholder: '输入要在车上播报的文字' })
          .fontSize(FG.bodySize)
          .fontColor(FG.text)
          .height(43)
          .width('100%')
          .padding({ left: 12, right: 12 })
          .borderRadius(8)
          .border({ width: 1, color: FG.inputBorder })
          .backgroundColor(FG.inputBg)
          .onChange((v: string) => { this.ttsText = v })

        Row() {
          Row() {
            Text('取消')
              .fontSize(FG.bodySize)
              .fontWeight(FontWeight.Bold)
              .fontColor(FG.text)
          }
          .layoutWeight(1)
          .height(42)
          .justifyContent(FlexAlign.Center)
          .borderRadius(FG.btnRadius)
          .backgroundColor(FG.btnDefault)
          .margin({ right: 5 })
          .onClick(() => { this.showTts = false })

          Row() {
            Text('播报')
              .fontSize(FG.bodySize)
              .fontWeight(FontWeight.Bold)
              .fontColor('#10151d')
          }
          .layoutWeight(1)
          .height(42)
          .justifyContent(FlexAlign.Center)
          .borderRadius(FG.btnRadius)
          .backgroundColor(FG.orange)
          .margin({ left: 5 })
          .onClick(() => { this.sendTts() })
        }
        .width('100%')
        .margin({ top: 16 })
      }
      .width(320)
      .padding(20)
      .borderRadius(FG.cardRadius)
      .border({ width: 1, color: FG.line })
      .backgroundColor('#101927')
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
    .backgroundColor('rgba(0, 0, 0, 0.5)')
  }

  /** 雷达：本地显隐开关 */
  @Builder
  radarToggleBtn() {
    Row() {
      Image($r('app.media.radar'))
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

  /** 地图：跳转地图导航页 */
  @Builder
  mapBtn() {
    Row() {
      Image($r('app.media.map'))
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
      router.pushUrl({ url: 'pages/ScreenMapNav' })
    })
  }

  /** 录音开关（长按触发）：REST 模式接 /api/audio/record */
  private async toggleRecording(): Promise<void> {
    if (BackendState.type !== BackendType.REST) {
      promptAction.showToast({ message: '录音需 REST 连接' })
      return
    }
    if (!this.recording) {
      const ok: boolean = await restApiClient.startRecord(0)
      if (ok) {
        this.recording = true
        promptAction.showToast({ message: '录音已开始（再次长按停止）' })
      } else {
        promptAction.showToast({ message: '录音启动失败' })
      }
    } else {
      const ok: boolean = await restApiClient.stopRecord()
      this.recording = false
      promptAction.showToast({ message: ok ? '录音已停止' : '停止录音失败' })
    }
  }

  /** TTS 喊话（单击触发）：REST 模式接 /api/audio/say */
  private async sendTts(): Promise<void> {
    if (BackendState.type !== BackendType.REST) {
      promptAction.showToast({ message: '喊话需 REST 连接' })
      return
    }
    if (this.ttsText.length === 0) {
      promptAction.showToast({ message: '请输入播报文字' })
      return
    }
    const ok: boolean = await restApiClient.sendTts(this.ttsText, 'zh')
    promptAction.showToast({ message: ok ? '已下发车端播报' : '播报失败' })
    if (ok) {
      this.showTts = false
      this.ttsText = ''
    }
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
    .position(this.radarPos())
  }

  /** 运动摇杆位置：自定义优先，否则默认左下锚定 */
  private movePos(): Position {
    if (ManualLayout.customized) {
      return { x: ManualLayout.moveXR * this.stageW, y: ManualLayout.moveYR * this.stageH }
    }
    return { x: 20, y: this.stageH - 120 - 14 }
  }

  /** 视角摇杆位置：自定义优先，否则默认右下锚定 */
  private viewPos(): Position {
    if (ManualLayout.customized) {
      return { x: ManualLayout.viewXR * this.stageW, y: ManualLayout.viewYR * this.stageH }
    }
    return { x: this.stageW - 140 - 16, y: this.stageH - 62 - 60 }
  }

  /** 雷达小窗位置：自定义优先，否则默认居中偏上 */
  private radarPos(): Position {
    if (ManualLayout.customized) {
      return { x: ManualLayout.radarXR * this.stageW, y: ManualLayout.radarYR * this.stageH }
    }
    return { x: (this.stageW - 140) / 2, y: Math.max(56, (this.stageH - 140) / 2 - 20) }
  }

  private getVideoUrl(): string {
    // 两种模式都直连 ROS2 web_video_server(视频端口，默认 8080) 原流
    return `http://${BackendState.ip}:${BackendState.videoPort}/stream?topic=/camera/color/image_raw`
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
