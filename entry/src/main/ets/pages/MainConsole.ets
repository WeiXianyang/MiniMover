/**
 * FireGuard 工业巡检 APP 主控制台
 * 承载 5 个屏幕（连接/主页/告警/配送/编队），
 * 顶部为可滚动的内容区，底部为固定的 5 项标签栏，整体套用手机框深色风格。
 */
import { FG } from '../fireguard/Theme'
import { FgTab, FG_TAB_LABELS, FG_TAB_ICONS } from '../fireguard/Tabs'
import { ScreenUtils } from '../utils/ScreenUtils'
import { ScreenConnect } from '../fireguard/screens/ScreenConnect'
import { ScreenHome } from '../fireguard/screens/ScreenHome'
import { ScreenAlert } from '../fireguard/screens/ScreenAlert'
import { ScreenDelivery } from '../fireguard/screens/ScreenDelivery'
import { ScreenFleet } from '../fireguard/screens/ScreenFleet'

@Entry
@Component
struct MainConsole {
  /** 当前选中的 tab，默认进入主页 */
  @State current: FgTab = FgTab.Home

  /** 顶部状态栏（电量/时间）安全区高度，vp。全屏布局下用作内容区顶部内边距，避免重叠 */
  @State topSafe: number = 0
  /** 底部导航条/手势指示条安全区高度，vp */
  @State bottomSafe: number = 0

  private tabList: FgTab[] = [
    FgTab.Connect, FgTab.Home, FgTab.Alert, FgTab.Delivery, FgTab.Fleet
  ]

  aboutToAppear(): void {
    let ctx = getContext(this)
    ScreenUtils.getStatusBarHeight(ctx).then((h: number) => this.topSafe = h)
    ScreenUtils.getBottomSafeHeight(ctx).then((h: number) => this.bottomSafe = h)
  }

  /** 切换屏幕 */
  private gotoTab = (tab: FgTab) => {
    this.current = tab
  }

  build() {
    Column() {
      // 内容区（可滚动）
      Scroll() {
        Column() {
          if (this.current == FgTab.Connect) {
            ScreenConnect({ gotoTab: this.gotoTab })
          } else if (this.current == FgTab.Home) {
            ScreenHome({ gotoTab: this.gotoTab })
          } else if (this.current == FgTab.Alert) {
            ScreenAlert({ gotoTab: this.gotoTab })
          } else if (this.current == FgTab.Delivery) {
            ScreenDelivery({ gotoTab: this.gotoTab })
          } else {
            ScreenFleet({ gotoTab: this.gotoTab })
          }
        }
        .width('100%')
        .padding({ left: 20, right: 20, top: this.topSafe + 20, bottom: 20 })
      }
      .layoutWeight(1)
      .width('100%')
      .align(Alignment.Top)
      .scrollBar(BarState.Off)
      .edgeEffect(EdgeEffect.Spring)

      // 底部标签栏
      this.tabbar()
    }
    .width('100%')
    .height('100%')
    .backgroundColor(FG.bg)
  }

  @Builder
  tabbar() {
    Row() {
      Row() {
        ForEach(this.tabList, (tab: FgTab) => {
          Column() {
            Image(FG_TAB_ICONS[tab])
              .width(16)
              .height(16)
              .fillColor(this.current == tab ? FG.orange : FG.muted)
            Text(FG_TAB_LABELS[tab])
              .fontSize(11)
              .fontWeight(FontWeight.Bold)
              .fontColor(this.current == tab ? FG.orange : FG.muted)
              .margin({ top: 3 })
          }
          .layoutWeight(1)
          .height(42)
          .borderRadius(12)
          .justifyContent(FlexAlign.Center)
          .alignItems(HorizontalAlign.Center)
          .backgroundColor(this.current == tab ? 'rgba(232, 139, 69, 0.08)' : Color.Transparent)
          .onClick(() => this.current = tab)
        }, (tab: FgTab) => tab.toString())
      }
      .width('100%')
      .padding(8)
      .borderRadius(18)
      .border({ width: 1, color: 'rgba(42, 61, 86, 0.9)' })
      .backgroundColor(FG.tabbarBg)
    }
    .width('100%')
    .padding({ left: 16, right: 16, bottom: this.bottomSafe + 16, top: 8 })
  }
}
