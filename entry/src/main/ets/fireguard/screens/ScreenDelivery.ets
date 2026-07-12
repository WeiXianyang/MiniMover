/**
 * S05 应急配送
 * 自动规划配送路径。数据后端接入后替换。
 */
import { FG } from '../Theme'
import { FgPageHead, FgCard, FgRow, FgBar, FgButton, FgStatus } from '../Widgets'
import { FgTab } from '../Tabs'

@Component
export struct ScreenDelivery {
  gotoTab: (tab: FgTab) => void = () => {}

  build() {
    Column() {
      FgPageHead({
        title: '应急配送',
        subtitle: '自动规划配送路径',
        pillText: '配送中',
        pillStatus: FgStatus.Green
      })

      FgCard() {
        FgRow({ label: '配送物资', value: '灭火器模型 / 急救包' })
        FgRow({ label: '起点', value: '应急物资点D' })
        FgRow({ label: '终点', value: '配电柜A', showBorder: false })
      }

      // 配送路径 recommend 卡片，带进度条
      Column() {
        Text('配送路径')
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .margin({ bottom: 8 })
        Text('D 点装载 → 主通道 → 配电柜A')
          .fontSize(FG.recommendSize)
          .fontWeight(FontWeight.Bold)
          .fontColor(FG.text)
          .lineHeight(FG.recommendSize * 1.35)
        FgBar({ percent: 68 })
        Text('已完成 68%，当前绕过临时障碍物后继续前进。')
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .lineHeight(FG.labelSize * 1.55)
          .margin({ top: 9 })
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
      .padding(15)
      .margin({ bottom: 14 })
      .borderRadius(FG.cardRadius)
      .border({ width: 1, color: 'rgba(255, 151, 72, 0.42)' })
      .linearGradient({
        angle: 135,
        colors: [['rgba(255, 151, 72, 0.17)', 0], [FG.cardBg, 1]]
      })

      FgCard() {
        FgRow({ label: '任务状态', value: '配送中' })
        FgRow({ label: '载荷舱', value: '已锁定' })
        FgRow({ label: '目标确认', value: '待现场人员签收', showBorder: false })
      }

      FgButton({
        text: '取消配送并返回待命点',
        onTap: () => this.gotoTab(FgTab.Home)
      })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }
}
