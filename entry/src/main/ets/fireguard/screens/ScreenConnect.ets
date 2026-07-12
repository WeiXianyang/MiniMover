/**
 * S01 设备连接
 * 保留真实 TCP 连接逻辑（来自原 NetworkSettings），套用 FireGuard 设计。
 */
import promptAction from '@ohos.promptAction'
import { FG } from '../Theme'
import { FgPageHead, FgCard, FgRow, FgButton, FgStatus, FgBtnType } from '../Widgets'
import { FgTab } from '../Tabs'
import { TCPClientManager } from '../../tcp/TCPClientManager'
import { TCPClientSendUtils } from '../../tcp/TCPClientSendUtils'
import { PreferencesUtils } from '../../utils/PreferencesUtils'
import { VideoComponents } from '../../components/VideoComponents'
import { MyUtils } from '../../utils/MyUtils'

@Component
export struct ScreenConnect {
  /** 切换到指定 tab（连接成功后进入主页） */
  gotoTab: (tab: FgTab) => void = () => {}

  @State ip: string = '192.168.1.11'
  @State tcpPort: string = '6000'
  @State videoPort: string = '6500'

  aboutToAppear(): void {
    this.readNetConfig()
  }

  build() {
    Column() {
      FgPageHead({
        title: '设备连接',
        subtitle: 'OpenHarmony 控制入口',
        pillText: '最近在线',
        pillStatus: FgStatus.Green
      })

      // 小车 IP
      Column() {
        Text('小车 IP')
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .margin({ bottom: 8 })
        TextInput({ text: this.ip })
          .fontSize(FG.bodySize)
          .fontColor(FG.text)
          .height(43)
          .width('100%')
          .padding({ left: 12, right: 12 })
          .borderRadius(8)
          .border({ width: 1, color: FG.inputBorder })
          .backgroundColor(FG.inputBg)
          .onChange((v: string) => this.ip = v)
      }
      .alignItems(HorizontalAlign.Start)
      .width('100%')
      .padding(14)
      .margin({ bottom: 14 })
      .borderRadius(FG.cardRadius)
      .border({ width: 1, color: FG.line })
      .backgroundColor(FG.cardBg)

      // TCP 控制端口
      Column() {
        Text('TCP 控制端口')
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .margin({ bottom: 8 })
        TextInput({ text: this.tcpPort })
          .fontSize(FG.bodySize)
          .fontColor(FG.text)
          .height(43)
          .width('100%')
          .padding({ left: 12, right: 12 })
          .borderRadius(8)
          .border({ width: 1, color: FG.inputBorder })
          .backgroundColor(FG.inputBg)
          .onChange((v: string) => this.tcpPort = v)
      }
      .alignItems(HorizontalAlign.Start)
      .width('100%')
      .padding(14)
      .margin({ bottom: 14 })
      .borderRadius(FG.cardRadius)
      .border({ width: 1, color: FG.line })
      .backgroundColor(FG.cardBg)

      // 视频端口
      Column() {
        Text('视频端口')
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .margin({ bottom: 8 })
        TextInput({ text: this.videoPort })
          .fontSize(FG.bodySize)
          .fontColor(FG.text)
          .height(43)
          .width('100%')
          .padding({ left: 12, right: 12 })
          .borderRadius(8)
          .border({ width: 1, color: FG.inputBorder })
          .backgroundColor(FG.inputBg)
          .onChange((v: string) => this.videoPort = v)
      }
      .alignItems(HorizontalAlign.Start)
      .width('100%')
      .padding(14)
      .margin({ bottom: 14 })
      .borderRadius(FG.cardRadius)
      .border({ width: 1, color: FG.line })
      .backgroundColor(FG.cardBg)

      FgCard() {
        FgRow({ label: '设备状态', value: 'Jetson / ROS2 / 视频服务正常' })
        FgRow({ label: '最近任务', value: '07-07 上午巡检' })
        FgRow({ label: '上次连接', value: '09:26', showBorder: false })
      }

      FgButton({
        text: '连接并进入巡检控制台',
        type: FgBtnType.Primary,
        onTap: () => { this.onConnect() }
      })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  private onConnect() {
    this.saveNetConfig()
    VideoComponents.ip = this.ip
    VideoComponents.port = Number.parseInt(this.videoPort)
    this.initTcpConfig()
  }

  private async initTcpConfig() {
    TCPClientManager.getInstance().initNetAddress({
      address: this.ip,
      port: Number.parseInt(this.tcpPort)
    })
    let isConnect = await TCPClientManager.getInstance().connect()
    if (isConnect) {
      promptAction.showToast({ message: '连接成功' })
      TCPClientSendUtils.getInstance().init()
      this.gotoTab(FgTab.Home)
    } else {
      promptAction.showToast({ message: '连接失败，请检查信息' })
      if (MyUtils.isDebug) {
        this.gotoTab(FgTab.Home)
      }
    }
  }

  private readNetConfig() {
    PreferencesUtils.getInstance().netUtils.getIP().then((v: string) => this.ip = v)
    PreferencesUtils.getInstance().netUtils.getTcpPort().then((v: string) => this.tcpPort = v)
    PreferencesUtils.getInstance().netUtils.getVideoPort().then((v: string) => this.videoPort = v)
  }

  private saveNetConfig() {
    PreferencesUtils.getInstance().netUtils.setIp(this.ip)
    PreferencesUtils.getInstance().netUtils.setTcpPort(this.tcpPort)
    PreferencesUtils.getInstance().netUtils.setVideoPort(this.videoPort)
  }
}
