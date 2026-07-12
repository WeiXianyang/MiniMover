/**
 * S03 地图导航
 * 实时路径与点位。地图以 Stack 绝对定位模拟原型的 CSS 画法，数据后端接入后替换。
 */
import { FG } from '../Theme'
import { FgPageHead, FgCard, FgRow, FgBar, FgButton, FgStatus } from '../Widgets'
import { FgTab } from '../Tabs'

@Component
export struct ScreenMap {
  gotoTab: (tab: FgTab) => void = () => {}

  build() {
    Column() {
      FgPageHead({
        title: '地图导航',
        subtitle: '实时路径与点位',
        pillText: '避障中',
        pillStatus: FgStatus.Orange
      })

      // 地图区域：网格背景 + 路径 + 点位 + 小车
      Stack() {
        // 横向路径 route-x
        Row()
          .width(168)
          .height(4)
          .borderRadius(FG.pillRadius)
          .backgroundColor(FG.cyan)
          .position({ x: 68, y: 82 })

        // 纵向路径 route-y
        Row()
          .width(4)
          .height(105)
          .borderRadius(FG.pillRadius)
          .backgroundColor(FG.cyan)
          .position({ x: 210, y: 82 })

        // 节点 A
        this.mapNode('A', 54, 69, FG.cyan, '#08202a')
        // 节点 B
        this.mapNode('B', 197, 69, FG.cyan, '#08202a')
        // 节点 C（告警点）
        this.mapNode('C', 197, 174, FG.red, '#ffffff')

        // 小车位置
        Row()
          .width(30)
          .height(30)
          .borderRadius(FG.pillRadius)
          .backgroundColor(FG.orange)
          .shadow({ radius: 20, color: 'rgba(255, 151, 72, 0.5)' })
          .position({ x: 127, y: 69 })
      }
      .width('100%')
      .height(250)
      .margin({ bottom: 12 })
      .borderRadius(FG.cardRadius)
      .clip(true)
      .backgroundColor('#132035')
      .alignContent(Alignment.TopStart)

      // 图例
      Row() {
        this.legendItem(FG.cyan, '当前路径')
        this.legendItem(FG.orange, '小车位置')
        this.legendItem(FG.red, '告警点')
      }
      .width('100%')
      .margin({ bottom: 14 })

      FgCard() {
        FgRow({ label: '巡检进度', value: '41%', showBorder: false })
        FgBar({ percent: 41 })
        Text('已到达 B2 区域，正在靠近配电柜 A。')
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .lineHeight(FG.labelSize * 1.55)
          .margin({ top: 9 })
      }

      Row() {
        Column() {
          FgButton({ text: '暂停任务', onTap: () => this.gotoTab(FgTab.Home) })
        }
        .layoutWeight(1)
        .margin({ right: 5 })

        Column() {
          FgButton({ text: '手动接管', onTap: () => this.gotoTab(FgTab.Manual) })
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
  mapNode(label: string, x: number, y: number, bg: string, fg: string) {
    Text(label)
      .fontSize(FG.smallSize)
      .fontWeight(FontWeight.Bolder)
      .fontColor(fg)
      .textAlign(TextAlign.Center)
      .width(30)
      .height(30)
      .borderRadius(FG.pillRadius)
      .backgroundColor(bg)
      .position({ x: x, y: y })
  }

  @Builder
  legendItem(dot: string, label: string) {
    Row() {
      Row()
        .width(8)
        .height(8)
        .borderRadius(FG.pillRadius)
        .backgroundColor(dot)
        .margin({ right: 5 })
      Text(label)
        .fontSize(FG.smallSize)
        .fontColor(FG.muted)
    }
    .margin({ right: 10 })
  }
}
