/**
 * S04 告警详情
 * 配电柜A疑似烟雾。数据后端接入后替换。
 * "远程接管"按钮导航至横屏手动接管页面。
 */
import router from '@ohos.router'
import { FG } from '../Theme'
import { FgPageHead, FgCard, FgRow, FgRecommend, FgButton, FgStatus, FgBtnType } from '../Widgets'
import { FgTab } from '../Tabs'

@Component
export struct ScreenAlert {
  gotoTab: (tab: FgTab) => void = () => {}

  build() {
    Column() {
      FgPageHead({
        title: '告警详情',
        subtitle: '配电柜A · 疑似烟雾',
        pillText: '高等级告警',
        pillStatus: FgStatus.Red
      })

      // 告警可视化区域（红色径向光晕）
      Stack()
        .width('100%')
        .height(172)
        .margin({ bottom: 14 })
        .borderRadius(FG.cardRadius)
        .border({ width: 1, color: 'rgba(255, 101, 112, 0.55)' })
        .backgroundColor('#162235')
        .radialGradient({
          center: ['54%', '38%'],
          radius: 44,
          colors: [['rgba(255, 101, 112, 0.26)', 0], ['rgba(255, 101, 112, 0)', 1]]
        })

      FgCard() {
        FgRow({ label: '识别类型', value: '疑似烟雾 / 明火风险' })
        FgRow({ label: '置信度', value: '91%' })
        FgRow({ label: '温度', value: '37°C', showBorder: false })
      }

      FgRecommend({
        label: '处置建议',
        title: '派发定点配送，并通知现场人员确认。'
      })

      Column({ space: 10 }) {
        FgButton({
          text: '发起定点配送',
          type: FgBtnType.Primary,
          onTap: () => { this.gotoTab(FgTab.Delivery) }
        })

        FgButton({
          text: '进入远程接管',
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
}
