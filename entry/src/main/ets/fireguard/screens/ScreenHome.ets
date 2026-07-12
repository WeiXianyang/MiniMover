/**
 * S02 巡检主页
 * 今日任务总览。数据暂为原型静态值，后端接入后替换。
 */
import { FgPageHead, FgCard, FgRow, FgMetric, FgRecommend, FgButton, FgStatus, FgBtnType } from '../Widgets'
import { FgTab } from '../Tabs'

@Component
export struct ScreenHome {
  gotoTab: (tab: FgTab) => void = () => {}

  build() {
    Column() {
      FgPageHead({
        title: '巡检主页',
        subtitle: '今日任务总览',
        pillText: '自动巡检待命',
        pillStatus: FgStatus.Green
      })

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
            text: '开始自动巡检',
            type: FgBtnType.Primary,
            onTap: () => this.gotoTab(FgTab.Map)
          })
        }
        .layoutWeight(1)
        .margin({ right: 5 })

        Column() {
          FgButton({
            text: '手动控制',
            onTap: () => this.gotoTab(FgTab.Manual)
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
}
