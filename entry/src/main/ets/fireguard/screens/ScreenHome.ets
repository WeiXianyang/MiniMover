/**
 * S02 巡检主页
 * 今日任务总览。根据连接状态显示不同内容。
 */
import router from '@ohos.router'
import { FgPageHead, FgCard, FgRow, FgMetric, FgRecommend, FgButton, FgStatus, FgBtnType } from '../Widgets'
import { FgTab } from '../Tabs'
import { BackendState } from '../../CarUtill/BackendType'

@Component
export struct ScreenHome {
  gotoTab: (tab: FgTab) => void = () => {}

  build() {
    Column() {
      FgPageHead({
        title: '巡检主页',
        subtitle: '车辆状态与任务入口',
        pillText: BackendState.connected ? '设备已连接' : '待命',
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
          FgMetric({ value: '86%', label: '电量' })
        }
        GridItem() {
          FgMetric({ value: '4', label: '待巡检点' })
        }
        GridItem() {
          FgMetric({ value: '正常', label: '烟雾值' })
        }
        GridItem() {
          FgMetric({ value: '29°C', label: '机柜环境温度' })
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

      Row() {
        Column() {
          FgButton({
            text: '开始巡检',
            type: FgBtnType.Primary,
            onTap: () => { this.gotoTab(FgTab.Delivery) }
          })
        }
        .layoutWeight(1)
        .margin({ right: 5 })

        Column() {
          FgButton({
            text: '切换到手动接管',
            onTap: () => {
              router.pushUrl({ url: 'pages/ScreenManualLandscape' })
            }
          })
        }
        .layoutWeight(1)
        .margin({ left: 5 })
      }
      .width('100%')
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
