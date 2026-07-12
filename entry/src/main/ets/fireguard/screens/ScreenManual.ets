/**
 * S06 手动接管
 * 异常情况下的人机协同。折叠了原 MecanumWheel / RemoteControl 的真实控制能力：
 * 按钮/摇杆驾驶、实时视频、拍摄/录制、自动循迹、四轮独立调速、急停。
 */
import promptAction from '@ohos.promptAction'
import { FG } from '../Theme'
import { FgPageHead, FgButton, FgStatus, FgBtnType } from '../Widgets'
import { FgTab } from '../Tabs'
import { carApi } from '../../CarUtill/CarApi'
import { CarEncode } from '../../CarUtill/CarEncode'
import { CarDirection } from '../../CarUtill/CarEnum'
import { VideoComponents } from '../../components/VideoComponents'
import { CarBtnComponents } from '../../components/CarBtnComponents'
import { CarRockerComponents } from '../../components/CarRockerComponents'

/** 手动接管的控制模式 */
enum ManualMode {
  Button = 0,
  Rocker = 1,
  Wheel = 2
}

@Component
export struct ScreenManual {
  gotoTab: (tab: FgTab) => void = () => {}

  /** 当前控制模式 */
  @State mode: ManualMode = ManualMode.Rocker
  /** 是否开启自动循迹 */
  @State tracking: boolean = false
  /** 四轮速度 */
  @State l1: number = 0
  @State l2: number = 0
  @State r1: number = 0
  @State r2: number = 0

  private modeList: ManualMode[] = [ManualMode.Button, ManualMode.Rocker, ManualMode.Wheel]
  private modeLabels: string[] = ['按钮', '摇杆', '四轮']

  build() {
    Column() {
      FgPageHead({
        title: '手动接管',
        subtitle: '异常情况下的人机协同',
        pillText: '接管中',
        pillStatus: FgStatus.Orange
      })

      // 实时视频
      VideoComponents()

      // 控制模式切换
      Row() {
        ForEach(this.modeList, (m: ManualMode, index: number) => {
          Text(this.modeLabels[index])
            .fontSize(FG.bodySize)
            .fontWeight(FontWeight.Bold)
            .fontColor(this.mode == m ? '#10151d' : FG.text)
            .textAlign(TextAlign.Center)
            .layoutWeight(1)
            .height(38)
            .backgroundColor(this.mode == m ? FG.orange : FG.btnDefault)
            .onClick(() => this.mode = m)
        }, (m: ManualMode) => m.toString())
      }
      .width('100%')
      .margin({ top: 14, bottom: 14 })
      .borderRadius(FG.btnRadius)
      .clip(true)

      // 控制区域
      Stack() {
        if (this.mode == ManualMode.Button) {
          CarBtnComponents()
        } else if (this.mode == ManualMode.Rocker) {
          CarRockerComponents()
        } else {
          this.wheelControl()
        }
      }
      .width('100%')
      .height(220)
      .margin({ bottom: 14 })

      // 自动循迹开关
      Row() {
        Text('自动循迹')
          .fontSize(FG.bodySize)
          .fontColor(FG.text)
          .layoutWeight(1)
        Toggle({ type: ToggleType.Switch, isOn: this.tracking })
          .selectedColor(FG.orange)
          .onChange((isOn: boolean) => {
            this.tracking = isOn
            if (isOn) {
              carApi.send(CarEncode.TrackingOpenEncode())
            } else {
              carApi.send(CarEncode.TrackingCloseEncode())
            }
          })
      }
      .width('100%')
      .padding(15)
      .margin({ bottom: 14 })
      .borderRadius(FG.cardRadius)
      .border({ width: 1, color: FG.line })
      .backgroundColor(FG.cardBg)

      // 录制 / 灯带
      Row() {
        Column() {
          FgButton({
            text: '录制现场视频',
            onTap: () => carApi.send(CarEncode.StartRecordingEncode())
          })
        }
        .layoutWeight(1)
        .margin({ right: 5 })

        Column() {
          FgButton({
            text: '切换灯带警示',
            onTap: () => promptAction.showToast({ message: '灯带警示（待后端接入）' })
          })
        }
        .layoutWeight(1)
        .margin({ left: 5 })
      }
      .width('100%')
      .margin({ bottom: 10 })

      // 急停
      FgButton({
        text: '急停',
        type: FgBtnType.Danger,
        onTap: () => {
          carApi.carBtnCtrl(CarDirection.Brake)
          this.gotoTab(FgTab.Home)
        }
      })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  /** 四轮独立调速控制 */
  @Builder
  wheelControl() {
    Column() {
      this.wheelSlider('左前轮', this.l1, (v: number) => this.l1 = v)
      this.wheelSlider('左后轮', this.l2, (v: number) => this.l2 = v)
      this.wheelSlider('右前轮', this.r1, (v: number) => this.r1 = v)
      this.wheelSlider('右后轮', this.r2, (v: number) => this.r2 = v)

      Row() {
        Column() {
          FgButton({
            text: '更新速度',
            type: FgBtnType.Primary,
            onTap: () => { this.sendSpeed() }
          })
        }
        .layoutWeight(1)
        .margin({ right: 5 })

        Column() {
          FgButton({
            text: '全部归零',
            onTap: () => {
              this.l1 = 0
              this.l2 = 0
              this.r1 = 0
              this.r2 = 0
              this.sendSpeed()
            }
          })
        }
        .layoutWeight(1)
        .margin({ left: 5 })
      }
      .width('100%')
      .margin({ top: 4 })
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }

  @Builder
  wheelSlider(label: string, value: number, onChange: (v: number) => void) {
    Row() {
      Text(label)
        .fontSize(FG.smallSize)
        .fontColor(FG.muted)
        .width(52)
      Slider({ value: value, min: -100, max: 100, style: SliderStyle.InSet })
        .blockColor(FG.orange)
        .trackColor(FG.barTrack)
        .selectedColor(FG.cyan)
        .layoutWeight(1)
        .onChange((v: number) => onChange(v))
      Text(`${value.toFixed(0)}`)
        .fontSize(FG.smallSize)
        .fontColor(FG.text)
        .textAlign(TextAlign.Center)
        .width(36)
    }
    .width('100%')
    .margin({ bottom: 4 })
  }

  private sendSpeed() {
    carApi.send(CarEncode.UpSpeedCarEncode(this.l1, this.l2, this.r1, this.r2))
  }
}
