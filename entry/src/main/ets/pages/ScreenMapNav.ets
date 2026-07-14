/**
 * S03 地图与任务（路由页）
 * 参照 map.html 原型。加载小车真实地图（/api/map_image），
 * 点选地图 → 依据 /api/map 元数据换算世界坐标 → POST /api/navigate 下发导航目标。
 * 仅 REST 模式可用；无位姿/进度接口，进度区显示操作提示而非假数据。
 */
import router from '@ohos.router'
import promptAction from '@ohos.promptAction'
import { FG } from '../fireguard/Theme'
import { FgPageHead, FgCard, FgButton, FgStatus } from '../fireguard/Widgets'
import { BackendState, BackendType } from '../CarUtill/BackendType'
import { restApiClient } from '../tcp/RestApiClient'
import { MapMeta } from '../tcp/CarModels'

@Entry
@Component
struct ScreenMapNav {
  /** 地图图片 URL（连接后填充） */
  @State mapUrl: string = ''
  /** 地图元数据，用于像素→世界坐标换算 */
  @State meta: MapMeta | null = null
  /** 地图区实际渲染尺寸（vp），用于点选换算 */
  @State mapW: number = 0
  @State mapH: number = 0
  /** 最近一次点选的目标标记（vp，地图区内相对坐标），-1 表示无 */
  @State markX: number = -1
  @State markY: number = -1
  /** 状态提示 */
  @State hint: string = '点选地图任意位置，下发导航目标'

  aboutToAppear(): void {
    if (BackendState.connected && BackendState.type === BackendType.REST) {
      this.mapUrl = restApiClient.getMapImageUrl()
      this.loadMeta()
    } else {
      this.hint = '未连接 REST 设备，地图不可用'
    }
  }

  private async loadMeta(): Promise<void> {
    const m: MapMeta | null = await restApiClient.getMapMeta()
    if (m !== null) {
      this.meta = m
    }
  }

  build() {
    Column() {
      // 顶部返回
      Row() {
        Image($r('app.media.arrow_left'))
          .width(18)
          .height(18)
          .fillColor(FG.text)
        Text('返回')
          .fontSize(FG.bodySize)
          .fontColor(FG.text)
          .margin({ left: 4 })
      }
      .height(32)
      .alignSelf(ItemAlign.Start)
      .margin({ bottom: 12 })
      .onClick(() => { router.back() })

      FgPageHead({
        title: '地图与任务',
        subtitle: '路径进度与障碍状态',
        pillText: this.meta !== null ? '地图就绪' : '避障中',
        pillStatus: this.meta !== null ? FgStatus.Green : FgStatus.Orange
      })

      // 地图区域
      Stack() {
        if (this.mapUrl.length > 0) {
          Image(this.mapUrl)
            .width('100%')
            .height('100%')
            .objectFit(ImageFit.Contain)
        } else {
          Text('地图不可用')
            .fontSize(FG.bodySize)
            .fontColor(FG.muted)
        }

        // 目标点标记
        if (this.markX >= 0) {
          Circle()
            .width(16)
            .height(16)
            .fill(FG.orange)
            .shadow({ radius: 10, color: 'rgba(255, 151, 72, 0.5)' })
            .position({ x: this.markX - 8, y: this.markY - 8 })
        }
      }
      .width('100%')
      .height(300)
      .margin({ bottom: 12 })
      .borderRadius(FG.cardRadius)
      .clip(true)
      .backgroundColor('#132035')
      .alignContent(Alignment.TopStart)
      .onAreaChange((_o: Area, n: Area) => {
        this.mapW = new Number(n.width).valueOf()
        this.mapH = new Number(n.height).valueOf()
      })
      .onClick((e: ClickEvent) => {
        this.onMapTap(e.x, e.y)
      })

      // 图例
      Row() {
        this.legendItem(FG.cyan, '当前路径')
        this.legendItem(FG.orange, '导航目标')
        this.legendItem(FG.red, '告警点')
      }
      .width('100%')
      .margin({ bottom: 14 })

      FgCard() {
        Text(this.hint)
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .lineHeight(FG.labelSize * 1.55)
      }

      Row() {
        Column() {
          FgButton({ text: '暂停任务', onTap: () => { router.back() } })
        }
        .layoutWeight(1)
        .margin({ right: 5 })

        Column() {
          FgButton({
            text: '手动接管',
            onTap: () => { router.pushUrl({ url: 'pages/ScreenManualLandscape' }) }
          })
        }
        .layoutWeight(1)
        .margin({ left: 5 })
      }
      .width('100%')
    }
    .width('100%')
    .height('100%')
    .padding(20)
    .backgroundColor(FG.bg)
    .alignItems(HorizontalAlign.Start)
  }

  /** 点选地图 → 换算世界坐标 → 下发导航 */
  private onMapTap(px: number, py: number): void {
    if (this.meta === null || this.mapW <= 0 || this.mapH <= 0) {
      promptAction.showToast({ message: '地图未就绪' })
      return
    }
    this.markX = px
    this.markY = py

    // 像素占比 → 栅格坐标（图片按 Contain 铺满区域，近似用区域尺寸换算）
    const meta: MapMeta = this.meta
    const col: number = (px / this.mapW) * meta.width
    // 图片行 0 在顶部，栅格 y 通常从底部向上，故翻转
    const rowFromBottom: number = (1 - py / this.mapH) * meta.height
    const worldX: number = meta.origin[0] + col * meta.resolution
    const worldY: number = meta.origin[1] + rowFromBottom * meta.resolution

    this.sendNavigate(worldX, worldY)
  }

  private async sendNavigate(x: number, y: number): Promise<void> {
    this.hint = `下发导航目标 (${x.toFixed(2)}, ${y.toFixed(2)}) ...`
    const ok: boolean = await restApiClient.sendNavigate(x, y, 0)
    if (ok) {
      this.hint = `已下发导航目标 (${x.toFixed(2)}, ${y.toFixed(2)})`
    } else {
      this.hint = '导航下发失败，请检查小车导航是否就绪'
      promptAction.showToast({ message: '导航下发失败' })
    }
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
