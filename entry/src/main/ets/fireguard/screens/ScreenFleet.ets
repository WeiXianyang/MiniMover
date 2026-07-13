/**
 * S05 编队管理
 * 多车编队控制页面。参照 fleet.html 原型，使用 SVG 图标。
 */
import promptAction from '@ohos.promptAction'
import { FG } from '../Theme'
import { FgPageHead, FgButton, FgStatus, FgBtnType } from '../Widgets'
import { FgTab } from '../Tabs'

/** 编队车辆数据结构 */
interface FleetVehicle {
  id: number
  name: string
  detail: string
  battery: number
  isLeader: boolean
}

@Component
export struct ScreenFleet {
  gotoTab: (tab: FgTab) => void = () => {}

  private vehicles: FleetVehicle[] = [
    { id: 1, name: '主车 · 队长', detail: '192.168.1.11 · 任务: 编队领航', battery: 86, isLeader: true },
    { id: 2, name: '从车 1', detail: '编队距离: 1.2m · 速度: 0.5 m/s', battery: 72, isLeader: false },
    { id: 3, name: '从车 2', detail: '编队距离: 1.5m · 速度: 0.5 m/s', battery: 65, isLeader: false }
  ]

  build() {
    Column() {
      FgPageHead({
        title: '车队编队',
        subtitle: '主车领航 · 从车跟随',
        pillText: '编队就绪',
        pillStatus: FgStatus.Green
      })

      // 车辆列表
      ForEach(this.vehicles, (v: FleetVehicle) => {
        Row() {
          // 车辆图标
          Row() {
            Image($r('app.media.car'))
              .width(18)
              .height(18)
              .fillColor(v.isLeader ? FG.orange : FG.muted)
          }
          .width(42)
          .height(42)
          .borderRadius(10)
          .backgroundColor(v.isLeader ? '#3a4454' : '#2e3746')
          .justifyContent(FlexAlign.Center)
          .margin({ right: 10 })

          // 车辆信息
          Column() {
            Text(v.name)
              .fontSize(16)
              .fontWeight(FontWeight.Bold)
              .fontColor(v.isLeader ? FG.orange : FG.text)
            Text(v.detail)
              .fontSize(FG.smallSize)
              .fontColor(FG.muted)
              .margin({ top: 5 })
          }
          .alignItems(HorizontalAlign.Start)
          .layoutWeight(1)

          // 电量状态徽标
          Row() {
            Row()
              .width(10)
              .height(10)
              .borderRadius(FG.pillRadius)
              .backgroundColor(FG.green)
              .margin({ right: 6 })
            Text(`${v.battery}%`)
              .fontSize(FG.smallSize)
              .fontWeight(FontWeight.Bold)
              .fontColor(FG.green)
          }
          .padding({ left: 12, right: 12, top: 6, bottom: 6 })
          .borderRadius(FG.pillRadius)
          .backgroundColor('rgba(99, 230, 167, 0.12)')
        }
        .width('100%')
        .padding(14)
        .margin({ bottom: 12 })
        .borderRadius(14)
        .border({ width: 1, color: v.isLeader ? FG.orange : '#2c3f57' })
        .backgroundColor('#1b2638')
      }, (v: FleetVehicle) => v.id.toString())

      // 添加从车按钮
      Row() {
        Text('+ 添加从车')
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('#a9b5c8')
      }
      .width('100%')
      .height(46)
      .justifyContent(FlexAlign.Center)
      .border({ width: 1, color: '#31445b', style: BorderStyle.Dashed })
      .borderRadius(14)
      .margin({ top: 10, bottom: 18 })
      .backgroundColor('rgba(19, 28, 42, 0.45)')
      .onClick(() => {
        promptAction.showToast({ message: '添加从车（待后端接入）' })
      })

      // 分隔线 + 编队命令
      Divider()
        .height(1)
        .color('rgba(147, 164, 186, 0.16)')
        .margin({ bottom: 14 })

      Text('编队命令')
        .fontSize(15)
        .fontWeight(FontWeight.Bold)
        .fontColor(FG.text)
        .margin({ bottom: 14 })
        .alignSelf(ItemAlign.Start)

      Row() {
        Column() {
          FgButton({
            icon: $r('app.media.play'),
            text: '出发',
            type: FgBtnType.Primary,
            onTap: () => {
              promptAction.showToast({ message: '编队出发（待后端接入）' })
            }
          })
        }
        .layoutWeight(1)
        .margin({ right: 5 })

        Column() {
          FgButton({
            icon: $r('app.media.square'),
            text: '停止',
            onTap: () => {
              promptAction.showToast({ message: '编队停止（待后端接入）' })
            }
          })
        }
        .layoutWeight(1)
        .margin({ left: 5 })
      }
      .width('100%')
      .margin({ bottom: 10 })

      // 解散编队（warning 风格）
      Row() {
        Row() {
          Image($r('app.media.unlink'))
            .width(18)
            .height(18)
            .fillColor('#ff6666')
          Text('解散编队')
            .fontSize(FG.bodySize)
            .fontWeight(FontWeight.Bold)
            .fontColor('#ff6666')
        }
        .justifyContent(FlexAlign.Center)
      }
      .width('100%')
      .height(46)
      .borderRadius(FG.btnRadius)
      .border({ width: 1, color: 'rgba(255, 101, 112, 0.28)' })
      .linearGradient({
        angle: 180,
        colors: [['rgba(65, 20, 20, 0.96)', 0], ['rgba(52, 16, 16, 0.96)', 1]]
      })
      .justifyContent(FlexAlign.Center)
      .onClick(() => {
        promptAction.showToast({ message: '解散编队（待后端接入）' })
      })

      // 分隔线 + 编队统计
      Divider()
        .height(1)
        .color('rgba(147, 164, 186, 0.16)')
        .margin({ top: 14, bottom: 14 })

      Text('编队统计')
        .fontSize(15)
        .fontWeight(FontWeight.Bold)
        .fontColor(FG.text)
        .margin({ bottom: 14 })
        .alignSelf(ItemAlign.Start)

      Row({ space: 10 }) {
        this.fleetStatItem('3', '车辆总数', FG.text)
        this.fleetStatItem('74%', '平均电量', FG.green)
        this.fleetStatItem('05s', '编队运行', FG.orange)
      }
      .width('100%')

      // 底部提示
      Text('左滑卡片移除从车 · 点击查看详情')
        .fontSize(FG.smallSize)
        .fontColor('rgba(147, 164, 186, 0.48)')
        .textAlign(TextAlign.Center)
        .width('100%')
        .margin({ top: 16 })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  fleetStatItem(value: string, label: string, valueColor: string) {
    Column() {
      Text(value)
        .fontSize(22)
        .fontWeight(FontWeight.Bold)
        .fontColor(valueColor)
      Text(label)
        .fontSize(FG.smallSize)
        .fontColor(FG.muted)
        .margin({ top: 8 })
    }
    .alignItems(HorizontalAlign.Start)
    .width('33%')
    .padding({ left: 10, right: 10, top: 12, bottom: 12 })
    .borderRadius(12)
    .border({ width: 1, color: '#2a3648' })
    .backgroundColor('rgba(26, 35, 50, 0.92)')
  }
}
