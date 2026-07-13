/**
 * S06b 手动接管布局设置
 * 参照 manual-settings.html 原型，横向全屏布局。
 * 可拖拽移动摇杆、雷达小窗、视角摇杆的布局位置。
 */
import promptAction from '@ohos.promptAction'
import router from '@ohos.router'
import { ScreenUtils } from '../utils/ScreenUtils'
import { FG } from '../fireguard/Theme'
import { CarDirection } from '../CarUtill/CarEnum'
import { carApi } from '../CarUtill/CarApi'
import { BackendState, BackendType } from '../CarUtill/BackendType'

@Entry
@Component
struct ScreenManualSettings {
  @State moveX: number = 28
  @State moveY: number = 215
  @State radarX: number = 240
  @State radarY: number = 120
  @State viewX: number = 620
  @State viewY: number = 226
  @State selected: string = ''
  @State stageW: number = 920
  @State stageH: number = 390

  aboutToAppear(): void {
    const ctx = getContext(this)
    ScreenUtils.setLandscape(ctx)
  }

  aboutToDisappear(): void {
    const ctx = getContext(this)
    ScreenUtils.setPortrait(ctx)
  }

  onBackPress(): boolean {
    return true
  }

  build() {
    Stack() {
      Column()
        .width('100%')
        .height('100%')
        .backgroundColor('#070b10')

      // 舞台区域
      Stack() {
        Column()
          .width('100%')
          .height('100%')
          .backgroundColor('rgba(255,255,255,0.02)')
          .linearGradient({
            angle: 180,
            colors: [
              ['rgba(13, 18, 28, 0.96)', 0],
              ['rgba(7, 10, 16, 0.98)', 1]
            ]
          })

        // ---- 拖拽节点：移动摇杆（120×120 圆 + 十字准星 + 橙色中心） ----
        Stack() {
          Circle().width(124).height(124)
            .fill('rgba(14, 22, 31, 0.62)')
            .stroke('rgba(147, 164, 186, 0.24)').strokeWidth(1)
          Line().width(1).height('100%')
            .stroke('rgba(147, 164, 186, 0.16)').strokeWidth(1)
          Line().width('100%').height(1)
            .stroke('rgba(147, 164, 186, 0.16)').strokeWidth(1)
          Circle().width(52).height(52).fill(FG.orange)
          Text('移动摇杆')
            .fontSize(11)
            .fontWeight(FontWeight.Bold)
            .fontColor(this.selected == 'move' ? FG.text : FG.muted)
            .position({ x: '50%', y: 94 })
            .translate({ x: '-50%', y: 0 })
        }
        .width(124)
        .height(124)
        .borderRadius(999)
        .border({
          width: this.selected == 'move' ? 3 : 1,
          color: this.selected == 'move' ? 'rgba(232, 139, 69, 0.72)' : 'rgba(147, 164, 186, 0.16)'
        })
        .backgroundColor(this.selected == 'move' ? 'rgba(28, 40, 55, 0.92)' : 'rgba(25, 35, 50, 0.72)')
        .shadow(this.selected == 'move' ?
          { radius: 3, color: 'rgba(232, 139, 69, 0.12)' } : { radius: 0 })
        .position({ x: this.moveX, y: this.moveY })
        .gesture(
          PanGesture({ direction: PanDirection.All })
            .onActionStart(() => { this.selected = 'move' })
            .onActionUpdate((event: GestureEvent) => {
              this.moveX = Math.max(0, Math.min(this.stageW - 124, this.moveStartX + event.offsetX))
              this.moveY = Math.max(0, Math.min(this.stageH - 124, this.moveStartY + event.offsetY))
            })
            .onActionEnd(() => { this.panStartSnapshot() })
        )
        .onClick(() => { this.selected = 'move' })

        // ---- 拖拽节点：雷达小窗（140×140 圆 + 雷达图标） ----
        Stack() {
          Circle().width(140).height(140)
            .fill('rgba(19, 28, 40, 0.48)')
            .stroke('rgba(147, 164, 186, 0.18)').strokeWidth(1)
          Circle().width(96).height(96)
            .fill(Color.Transparent)
            .stroke('rgba(147, 164, 186, 0.12)').strokeWidth(1)
          Line().width(54).height(1)
            .stroke('rgba(48, 211, 255, 0.5)').strokeWidth(1)
            .rotate({ angle: -32 })
          Circle().width(7).height(7).fill(FG.orange)
            .position({ x: 98, y: 45 })
          Image($r('app.media.radar')).width(22).height(22).fillColor(FG.cyan)
          Text('雷达小窗')
            .fontSize(11)
            .fontWeight(FontWeight.Bold)
            .fontColor(this.selected == 'radar' ? FG.text : FG.muted)
            .position({ x: '50%', y: 114 })
            .translate({ x: '-50%', y: 0 })
        }
        .width(140)
        .height(140)
        .borderRadius(999)
        .border({
          width: this.selected == 'radar' ? 3 : 1,
          color: this.selected == 'radar' ? 'rgba(232, 139, 69, 0.72)' : 'rgba(147, 164, 186, 0.16)'
        })
        .backgroundColor(this.selected == 'radar' ? 'rgba(28, 40, 55, 0.92)' : 'rgba(25, 35, 50, 0.72)')
        .shadow(this.selected == 'radar' ?
          { radius: 3, color: 'rgba(232, 139, 69, 0.12)' } : { radius: 0 })
        .position({ x: this.radarX, y: this.radarY })
        .gesture(
          PanGesture({ direction: PanDirection.All })
            .onActionStart(() => { this.selected = 'radar' })
            .onActionUpdate((event: GestureEvent) => {
              this.radarX = Math.max(0, Math.min(this.stageW - 140, this.radarStartX + event.offsetX))
              this.radarY = Math.max(0, Math.min(this.stageH - 140, this.radarStartY + event.offsetY))
            })
            .onActionEnd(() => { this.panStartSnapshot() })
        )
        .onClick(() => { this.selected = 'radar' })

        // ---- 拖拽节点：视角摇杆（药丸形 148×52 + 橙色中心） ----
        Stack() {
          Row()
            .width(148)
            .height(52)
            .borderRadius(999)
            .border({ width: 1, color: 'rgba(147, 164, 186, 0.24)' })
            .backgroundColor('rgba(14, 22, 31, 0.62)')
          Circle().width(52).height(52).fill(FG.orange)
          Text('视角摇杆')
            .fontSize(11)
            .fontWeight(FontWeight.Bold)
            .fontColor(this.selected == 'view' ? FG.text : FG.muted)
            .position({ x: '50%', y: 62 })
            .translate({ x: '-50%', y: 0 })
        }
        .width(148)
        .height(52)
        .borderRadius(999)
        .border({
          width: this.selected == 'view' ? 3 : 1,
          color: this.selected == 'view' ? 'rgba(232, 139, 69, 0.72)' : 'rgba(147, 164, 186, 0.16)'
        })
        .backgroundColor(this.selected == 'view' ? 'rgba(28, 40, 55, 0.92)' : 'rgba(25, 35, 50, 0.72)')
        .shadow(this.selected == 'view' ?
          { radius: 3, color: 'rgba(232, 139, 69, 0.12)' } : { radius: 0 })
        .position({ x: this.viewX, y: this.viewY })
        .gesture(
          PanGesture({ direction: PanDirection.All })
            .onActionStart(() => { this.selected = 'view' })
            .onActionUpdate((event: GestureEvent) => {
              this.viewX = Math.max(0, Math.min(this.stageW - 148, this.viewStartX + event.offsetX))
              this.viewY = Math.max(0, Math.min(this.stageH - 52, this.viewStartY + event.offsetY))
            })
            .onActionEnd(() => { this.panStartSnapshot() })
        )
        .onClick(() => { this.selected = 'view' })

        // 右侧工具列
        Column({ space: 8 }) {
          this.iconItem($r('app.media.lightbulb'))
          this.iconItem($r('app.media.mic'))
          this.iconItem($r('app.media.record'))
          this.iconItem($r('app.media.map'))
          this.iconItem($r('app.media.signal'))
        }
        .position({ x: this.stageW - 54, y: 92 })

        // 提示文字
        Text('点击选中 · 拖拽移动 · 滑动微调参数')
          .fontSize(11)
          .fontColor(FG.muted)
          .position({ x: 46, y: 56 })
      }
      .width('100%')
      .layoutWeight(1)
      .borderRadius(4)
      .border({ width: 1, color: '#1c2c41' })
      .onAreaChange((oldValue: Area, newValue: Area) => {
        this.stageW = new Number(newValue.width).valueOf()
        this.stageH = new Number(newValue.height).valueOf()
      })

      // 顶栏头部
      Row() {
        Row() {
          Image($r('app.media.arrow_left'))
            .width(18)
            .height(18)
            .fillColor(FG.text)
          Text('布局设置')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor(FG.text)
            .margin({ left: 8 })
        }
        .onClick(() => { router.back() })
      }
      .width('100%')
      .height(44)
      .padding({ left: 16, right: 16 })
      .alignItems(VerticalAlign.Center)
      .border({ width: { bottom: 1 }, color: 'rgba(147, 164, 186, 0.12)' })
      .backgroundColor('rgba(7, 12, 19, 0.88)')

      // 底部操作栏
      Row() {
        Row() {
          Image($r('app.media.rotate_ccw'))
            .width(16)
            .height(16)
            .fillColor('#ff5f66')
          Text('重置默认')
            .fontSize(12)
            .fontWeight(FontWeight.Bold)
            .fontColor('#ff5f66')
            .margin({ left: 7 })
        }
        .height(28)
        .padding({ left: 12, right: 12 })
        .borderRadius(8)
        .border({ width: 1, color: 'rgba(255, 101, 112, 0.34)' })
        .onClick(() => {
          this.resetDefault()
        })

        Row() {
          Image($r('app.media.save'))
            .width(16)
            .height(16)
            .fillColor('#10151d')
          Text('保存并应用')
            .fontSize(12)
            .fontWeight(FontWeight.Bold)
            .fontColor('#10151d')
            .margin({ left: 7 })
        }
        .height(28)
        .padding({ left: 12, right: 12 })
        .borderRadius(8)
        .backgroundColor(FG.orange)
        .onClick(() => {
          promptAction.showToast({ message: '布局已保存' })
          router.back()
        })
      }
      .width('100%')
      .height(44)
      .justifyContent(FlexAlign.SpaceBetween)
      .alignItems(VerticalAlign.Center)
      .padding({ left: 16, right: 16 })
      .border({ width: { top: 1 }, color: 'rgba(147, 164, 186, 0.12)' })
      .backgroundColor('rgba(7, 12, 19, 0.88)')
      .position({ x: 0, y: '100%' })
      .translate({ x: 0, y: -44 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#070b10')
  }

  @Builder
  iconItem(icon: Resource) {
    Row() {
      Image(icon)
        .width(18)
        .height(18)
        .fillColor(FG.muted)
    }
    .width(42)
    .height(42)
    .borderRadius(10)
    .border({ width: 1, color: 'rgba(147, 164, 186, 0.14)' })
    .backgroundColor('rgba(28, 37, 50, 0.86)')
    .justifyContent(FlexAlign.Center)
  }

  private moveStartX: number = 28
  private moveStartY: number = 215
  private radarStartX: number = 240
  private radarStartY: number = 120
  private viewStartX: number = 620
  private viewStartY: number = 226

  private panStartSnapshot(): void {
    this.moveStartX = this.moveX
    this.moveStartY = this.moveY
    this.radarStartX = this.radarX
    this.radarStartY = this.radarY
    this.viewStartX = this.viewX
    this.viewStartY = this.viewY
  }

  private resetDefault(): void {
    this.moveX = 28
    this.moveY = 215
    this.radarX = 240
    this.radarY = 120
    this.viewX = 620
    this.viewY = 226
    this.panStartSnapshot()
    this.selected = ''
    promptAction.showToast({ message: '已重置默认布局' })
  }
}
