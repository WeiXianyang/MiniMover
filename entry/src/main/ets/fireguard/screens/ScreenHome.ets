/**
 * S02 巡检主页
 * 今日任务总览。连接后（REST 模式）轮询 /api/status 显示真实电量/烟雾/温度。
 */
import router from '@ohos.router'
import { FgPageHead, FgCard, FgRow, FgMetric, FgRecommend, FgButton, FgStatus, FgBtnType } from '../Widgets'
import { FgTab } from '../Tabs'
import { BackendState, BackendType } from '../../CarUtill/BackendType'
import { restApiClient } from '../../tcp/RestApiClient'
import { CarStatus } from '../../tcp/CarModels'

@Component
export struct ScreenHome {
  gotoTab: (tab: FgTab) => void = () => {}

  /** 电量百分比（估算），未取到显示 -- */
  @State batteryText: string = '--'
  /** 烟雾值：正常 / 数值，未取到显示 -- */
  @State smokeText: string = '--'
  /** 机柜环境温度，未取到显示 -- */
  @State tempText: string = '--'
  /** 数据是否已成功获取，决定副标题状态 */
  @State telemetryOk: boolean = false

  private pollTimer: number = -1

  aboutToAppear(): void {
    if (BackendState.connected && BackendState.type === BackendType.REST) {
      this.refreshStatus()
      this.pollTimer = setInterval(() => {
        this.refreshStatus()
      }, 3000)
    }
  }

  aboutToDisappear(): void {
    if (this.pollTimer !== -1) {
      clearInterval(this.pollTimer)
      this.pollTimer = -1
    }
  }

  private async refreshStatus(): Promise<void> {
    const status: CarStatus | null = await restApiClient.getStatus()
    if (status !== null) {
      this.telemetryOk = true
      // 电池电压 → 百分比估算（3S 锂电：约 9.0V 空 ~ 12.6V 满）
      const pct: number = Math.round(Math.max(0, Math.min(100, ((status.battery - 9.0) / (12.6 - 9.0)) * 100)))
      this.batteryText = `${pct}%`
      this.smokeText = status.sensors.smoke > 0 ? `${status.sensors.smoke}` : '正常'
      this.tempText = `${status.sensors.temperature.toFixed(0)}°C`
    } else {
      this.telemetryOk = false
    }
  }

  build() {
    Column() {
      FgPageHead({
        title: '巡检主页',
        subtitle: '车辆状态与任务入口',
        pillText: BackendState.connected ? (this.telemetryOk ? '设备已连接' : '连接中') : '待命',
        pillStatus: BackendState.connected ? FgStatus.Green : FgStatus.Red
      })

      if (BackendState.connected) {
        this.buildConnected()
      } else {
        this.buildDisconnected()
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  buildConnected() {
    Column() {
      FgCard() {
        FgRow({ label: '当前区域', value: '园区 A 栋一层' })
        FgRow({ label: '当前任务', value: '配电房与仓储通道巡检', showBorder: false })
      }

      Grid() {
        GridItem() {
          FgMetric({ value: this.batteryText, label: '电量' })
        }
        GridItem() {
          FgMetric({ value: '--', label: '待巡检点' })
        }
        GridItem() {
          FgMetric({ value: this.smokeText, label: '烟雾值' })
        }
        GridItem() {
          FgMetric({ value: this.tempText, label: '机柜环境温度' })
        }
      }
      .columnsTemplate('1fr 1fr')
      .rowsGap(12)
      .columnsGap(12)
      .width('100%')
      .height(176)
      .margin({ bottom: 14 })

      FgRecommend({
        label: '推荐动作',
        title: '开始自动巡检，预计 6 分钟完成'
      })

      Column({ space: 10 }) {
        FgButton({
          text: '开始巡检',
          type: FgBtnType.Primary,
          onTap: () => {
            router.pushUrl({ url: 'pages/ScreenMapNav' })
          }
        })

        FgButton({
          text: '切换到手动接管',
          onTap: () => {
            router.pushUrl({ url: 'pages/ScreenManualLandscape' })
          }
        })
      }
      .width('100%')
      .margin({ top: 10 })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  buildDisconnected() {
    Column() {
      FgRecommend({
        label: '设备状态',
        title: '未连接到设备',
        desc: '请先完成设备连接，再开始巡检或进入手动接管。'
      })

      FgButton({
        text: '未连接到设备',
        onTap: () => { this.gotoTab(FgTab.Connect) }
      })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }
}
