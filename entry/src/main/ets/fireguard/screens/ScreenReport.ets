/**
 * S07 巡检报告
 * 一次任务结束后的摘要视图。数据后端接入后替换。
 */
import promptAction from '@ohos.promptAction'
import { FgPageHead, FgCard, FgRow, FgMetric, FgRecommend, FgButton, FgStatus } from '../Widgets'
import { FgTab } from '../Tabs'

@Component
export struct ScreenReport {
  gotoTab: (tab: FgTab) => void = () => {}

  build() {
    Column() {
      FgPageHead({
        title: '巡检报告',
        subtitle: '一次任务结束后的摘要视图',
        pillText: '已归档',
        pillStatus: FgStatus.Green
      })

      Grid() {
        GridItem() {
          FgMetric({ value: '6m 28s', label: '巡检耗时' })
        }
        GridItem() {
          FgMetric({ value: '4/4', label: '完成点位' })
        }
        GridItem() {
          FgMetric({ value: '1 次', label: '高等级告警' })
        }
        GridItem() {
          FgMetric({ value: '2 次', label: '动态避障' })
        }
      }
      .columnsTemplate('1fr 1fr')
      .rowsGap(12)
      .columnsGap(12)
      .width('100%')
      .height(176)
      .margin({ bottom: 14 })

      FgCard() {
        FgRow({ label: '事件 01', value: '配电柜A 发现疑似烟雾' })
        FgRow({ label: '事件 02', value: '仓储通道纸箱避障成功' })
        FgRow({ label: '处理结果', value: '应急配送完成，车辆已返航', showBorder: false })
      }

      FgRecommend({
        title: '导出能力',
        desc: '支持导出图片、视频片段、任务时间线和组会汇报摘要。'
      })

      Row() {
        Column() {
          FgButton({
            text: '导出 PDF',
            onTap: () => promptAction.showToast({ message: '导出 PDF（待后端接入）' })
          })
        }
        .layoutWeight(1)
        .margin({ right: 5 })

        Column() {
          FgButton({
            text: '分享报告',
            onTap: () => promptAction.showToast({ message: '分享报告（待后端接入）' })
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
