/**
 * S05 定点配送 / 巡逻导航
 * 对接车端 /api/nav/patrol/*。移动端不逐点点击地图（体验太差），
 * 改为：拉取车端已保存路线 → 点击选中 → 自动设为当前路线 → 开始巡逻。
 */
import router from '@ohos.router'
import promptAction from '@ohos.promptAction'
import { FG } from '../Theme'
import { FgPageHead, FgCard, FgRow, FgBar, FgButton, FgStatus, FgBtnType, FgRecommend } from '../Widgets'
import { FgTab } from '../Tabs'
import { restApiClient } from '../../tcp/RestApiClient'
import { PatrolStatus, PatrolRoute, NavStackStatus, Waypoint, LinkedWaypoint, RouteNameItem, NavMapMeta } from '../../tcp/NavModels'
import { PRESET_POINTS, PresetPoint, pointsToPresets, mergePresets, PixelPoint, MapPixel } from '../../CarUtill/PatrolPresets'

@Component
export struct ScreenDelivery {
  gotoTab: (tab: FgTab) => void = () => {}

  @State patrolStatus: PatrolStatus | null = null
  @State patrolRoute: PatrolRoute | null = null
  @State stackStatus: NavStackStatus | null = null
  /** 车端已保存的路线名列表 */
  @State savedRoutes: RouteNameItem[] = []
  /** 当前选中的路线名（高亮），空=未选 */
  @State selectedRoute: string = ''
  /** 操作中（正在选中/设置路线） */
  @State busy: boolean = false
  @State loading: boolean = true

  /** 自选路线途经点列表 */
  @State customPoints: LinkedWaypoint[] = []

  /** 预设可选点（用户可编辑的静态预设 + 车端路线途经点合并去重） */
  @State presetPoints: PresetPoint[] = PRESET_POINTS

  /** 用户可编辑的静态预设点基准（编辑写入这里，refresh 以它为合并基准，不被静态常量覆盖） */
  @State editablePresets: PresetPoint[] = PRESET_POINTS.map((p: PresetPoint): PresetPoint =>
    ({ x: p.x, y: p.y, label: p.label, source: p.source }))

  // ---- 编辑预设点 ----
  @State editing: boolean = false
  @State editX: string = ''
  @State editY: string = ''
  @State editLabel: string = ''
  @State editIdx: number = -1

  // ---- 地图预览 ----
  @State mapMeta: NavMapMeta | null = null
  @State mapUrl: string = ''

  private pollTimer: number = -1

  aboutToAppear(): void {
    this.refreshAll()
    this.pollTimer = setInterval(() => { this.refreshAll() }, 4000)
  }

  aboutToDisappear(): void {
    if (this.pollTimer !== -1) {
      clearInterval(this.pollTimer)
      this.pollTimer = -1
    }
  }

  private async refreshAll(): Promise<void> {
    // 核心状态：拉完就立即解除 loading，避免后续可选请求超时把页面卡在"正在连接"
    const ps: PatrolStatus | null = await restApiClient.getPatrolStatus()
    const ss: NavStackStatus | null = await restApiClient.getStackStatus()
    this.patrolStatus = ps
    this.stackStatus = ss
    this.loading = false

    // 以下为可选数据，失败不影响页面展示
    const pr: PatrolRoute | null = await restApiClient.getPatrolRoute()
    const sr: RouteNameItem[] = await restApiClient.getPatrolRoutes()
    this.patrolRoute = pr
    this.savedRoutes = sr

    // 从车端已保存路线中提取途经点，与"用户可编辑的预设点"合并去重
    const routeLists: PresetPoint[][] = [this.editablePresets]
    for (let i = 0; i < sr.length; i++) {
      const detail: PatrolRoute | null = await restApiClient.getPatrolRouteDetail(sr[i].name)
      if (detail !== null && detail.points.length > 0) {
        routeLists.push(pointsToPresets(detail.points, sr[i].name))
      }
    }
    this.presetPoints = mergePresets(...routeLists)

    // 拉取地图元数据 + 图片（用于路线预览坐标换算）
    const meta: NavMapMeta | null = await restApiClient.getNavMapMeta()
    if (meta !== null) {
      this.mapMeta = meta
      this.mapUrl = restApiClient.getNavMapImageUrl()
    }
  }

  private labelForStatus(s: PatrolStatus | null): string {
    if (s === null) return '未就绪'
    if (s.patrol_active) return '巡逻中'
    return '待命'
  }

  private pillForStatus(s: PatrolStatus | null): FgStatus {
    if (s === null) return FgStatus.Red
    if (s.patrol_active) return FgStatus.Orange
    return FgStatus.Green
  }

  build() {
    Column() {
      FgPageHead({
        title: '定点配送',
        subtitle: this.stackStatus !== null ? this.stackStatus.stack_message : '应急物资调度',
        pillText: this.labelForStatus(this.patrolStatus),
        pillStatus: this.pillForStatus(this.patrolStatus)
      })

      if (this.loading) {
        FgCard() {
          FgRow({ label: '提示', value: '正在连接导航服务…', showBorder: false })
        }
      } else {
        this.buildReady()
      }

      // 编辑弹窗浮层
      if (this.editing) {
        this.editDialog()
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  buildReady() {
    Column() {
      // 导航栈未就绪提示
      if (this.stackStatus !== null && !this.stackStatus.stack_ready) {
        FgRecommend({
          label: '导航栈',
          title: this.stackStatus.hint !== null && this.stackStatus.hint.length > 0
            ? this.stackStatus.hint : '导航栈未就绪，请先启动'
        })
      }

      // ===== 已保存路线列表（方案选择，替代逐点点击地图） =====
      if (this.savedRoutes.length > 0) {
        Text('选择配送方案')
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .margin({ bottom: 8 })

        ForEach(this.savedRoutes, (r: RouteNameItem) => {
          Row() {
            Column() {
              Text(r.name)
                .fontSize(FG.bodySize)
                .fontWeight(FontWeight.Bold)
                .fontColor(this.selectedRoute === r.name ? FG.orange : FG.text)
              Text('点击选中，设为当前配送路线')
                .fontSize(FG.smallSize)
                .fontColor(FG.muted)
                .margin({ top: 3 })
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)

            if (this.selectedRoute === r.name) {
              Text('已选中')
                .fontSize(FG.smallSize)
                .fontWeight(FontWeight.Bold)
                .fontColor('#10151d')
                .padding({ left: 10, right: 10, top: 4, bottom: 4 })
                .borderRadius(FG.pillRadius)
                .backgroundColor(FG.orange)
            }
          }
          .width('100%')
          .padding(14)
          .margin({ bottom: 8 })
          .borderRadius(FG.cardRadius)
          .border({ width: 1, color: this.selectedRoute === r.name ? FG.orange : FG.line })
          .backgroundColor(FG.cardBg)
          .onClick(() => { this.selectRoute(r.name) })
        }, (r: RouteNameItem) => r.name)
      } else {
        FgCard() {
          FgRow({ label: '提示', value: '暂无已保存的配送方案', showBorder: false })
        }
      }

      // ===== 自选固定点建路线 =====
      Row()
        .width('100%')
        .height(1)
        .backgroundColor('rgba(147, 164, 186, 0.16)')
        .margin({ top: 14, bottom: 14 })

      Text('自选巡检路线')
        .fontSize(15)
        .fontWeight(FontWeight.Bold)
        .fontColor(FG.text)
        .margin({ bottom: 10 })

      // 可选点网格（2 列）
      Grid() {
        ForEach(this.presetPoints, (p: PresetPoint) => {
          GridItem() {
            Column() {
              Text(p.source === 'route' ? `🛣 ${p.label}` : p.label)
                .fontSize(FG.bodySize)
                .fontWeight(FontWeight.Bold)
                .fontColor(FG.text)
              Text(`(${p.x.toFixed(1)}, ${p.y.toFixed(1)})`)
                .fontSize(FG.smallSize)
                .fontColor(FG.muted)
                .margin({ top: 2 })
            }
            .width('100%')
            .height(52)
            .justifyContent(FlexAlign.Center)
            .alignItems(HorizontalAlign.Center)
            .borderRadius(8)
            .border({ width: 1, color: FG.line })
            .backgroundColor(p.source === 'route' ? '#1a2a3a' : FG.btnDefault)
            .gesture(
              GestureGroup(GestureMode.Exclusive,
                LongPressGesture({ repeat: false })
                  .onAction(() => {
                    const fi: number = this.presetPoints.findIndex((pt: PresetPoint) => pt.label === p.label
                      && Math.abs(pt.x - p.x) < 0.01 && Math.abs(pt.y - p.y) < 0.01)
                    if (fi >= 0) { this.openEdit(fi) }
                  }),
                TapGesture()
                  .onAction(() => { this.addCustomPoint(p) })
              )
            )
          }
        }, (p: PresetPoint) => p.label)
      }
      .columnsTemplate('1fr 1fr')
      .rowsGap(6)
      .columnsGap(8)
      .width('100%')
      .height(this.presetPoints.length > 0 ? 52 * Math.ceil(this.presetPoints.length / 2) + 6 : 52)
      .margin({ bottom: 12 })

      // 当前自选路线
      if (this.customPoints.length > 0) {
        Column() {
          Text(`自选路线 · ${this.customPoints.length} 个点`)
            .fontSize(FG.bodySize)
            .fontWeight(FontWeight.Bold)
            .fontColor(FG.orange)
            .margin({ bottom: 6 })

          // 路线预览：地图 + 点 + 有向箭头
          if (this.mapUrl.length > 0 && this.mapMeta !== null) {
            this.routePreview()
          }

          ForEach(this.customPoints, (p: LinkedWaypoint, idx: number) => {
            Row() {
              Text(`${idx + 1}. ${p.label}`)
                .fontSize(FG.labelSize)
                .fontColor(FG.text)
                .layoutWeight(1)
              Text('×')
                .fontSize(FG.labelSize)
                .fontColor(FG.red)
                .width(24)
                .textAlign(TextAlign.Center)
                .onClick(() => { this.removeCustomPoint(idx) })
            }
            .width('100%')
            .padding({ top: 4, bottom: 4 })
          }, (p: LinkedWaypoint, idx: number) => `${idx}`)

          Row() {
            Row() {
              Text('清空')
                .fontSize(FG.bodySize)
                .fontWeight(FontWeight.Bold)
                .fontColor(FG.text)
            }
            .layoutWeight(1)
            .height(38)
            .justifyContent(FlexAlign.Center)
            .borderRadius(FG.btnRadius)
            .backgroundColor(FG.btnDefault)
            .margin({ right: 5 })
            .onClick(() => { this.customPoints = new Array<LinkedWaypoint>(); this.selectedRoute = '' })

            Row() {
              Text('设为此路线')
                .fontSize(FG.bodySize)
                .fontWeight(FontWeight.Bold)
                .fontColor('#10151d')
            }
            .layoutWeight(1)
            .height(38)
            .justifyContent(FlexAlign.Center)
            .borderRadius(FG.btnRadius)
            .backgroundColor(FG.orange)
            .margin({ left: 5 })
            .onClick(() => { this.applyCustomRoute() })
          }
          .width('100%')
          .margin({ top: 8, bottom: 14 })
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        .padding(12)
        .borderRadius(FG.cardRadius)
        .border({ width: 1, color: 'rgba(255, 151, 72, 0.28)' })
        .backgroundColor('rgba(255, 151, 72, 0.06)')
        .margin({ bottom: 14 })
      }

      // ===== 当前路线详情 =====
      if (this.patrolRoute !== null && this.patrolRoute.point_count > 0) {
        Column() {
          Text('当前路线')
            .fontSize(FG.labelSize)
            .fontColor(FG.muted)
            .margin({ bottom: 8 })

          Text(`${this.patrolRoute.point_count} 个途经点${this.patrolRoute.loop ? ' · 循环' : ''}`)
            .fontSize(FG.recommendSize)
            .fontWeight(FontWeight.Bold)
            .fontColor(FG.text)

          ForEach(this.patrolRoute.points, (wp: Waypoint, idx: number) => {
            Text(`途经点 ${idx + 1}: (${wp.x.toFixed(2)}, ${wp.y.toFixed(2)})`)
              .fontSize(FG.labelSize)
              .fontColor(FG.muted)
              .margin({ top: 4 })
          }, (_wp: Waypoint, idx: number) => idx.toString())

          if (this.patrolStatus !== null && this.patrolStatus.patrol_active) {
            FgBar({ percent: this.patrolRoute.point_count > 0
              ? this.patrolPercent() : 0 })
            Text(this.patrolStatus.status)
              .fontSize(FG.labelSize)
              .fontColor(FG.muted)
              .margin({ top: 9 })
          }
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
      }

      // 任务状态
      FgCard() {
        FgRow({
          label: '任务状态',
          value: this.patrolStatus !== null && this.patrolStatus.patrol_active
            ? this.patrolStatus.status : '待命'
        })
        FgRow({
          label: '导航栈',
          value: this.stackStatus !== null && this.stackStatus.stack_ready ? '已就绪' : '未就绪'
        })
        FgRow({
          label: '路线点数',
          value: this.patrolRoute !== null ? `${this.patrolRoute.point_count}` : '未设置',
          showBorder: false
        })
      }

      // 操作按钮
      Column({ space: 10 }) {
        if (this.stackStatus !== null && !this.stackStatus.stack_ready) {
          FgButton({
            text: '启动导航栈',
            type: FgBtnType.Primary,
            onTap: () => { this.startStack() }
          })
        } else if (this.selectedRoute.length > 0 && this.busy) {
          FgButton({ text: '设置中…', onTap: () => {} })
        } else if (this.patrolRoute !== null && this.patrolRoute.point_count > 0) {
          if (this.patrolStatus !== null && this.patrolStatus.patrol_active) {
            FgButton({
              text: '停止巡逻',
              type: FgBtnType.Danger,
              onTap: () => { this.doStopPatrol() }
            })
          } else {
            FgButton({
              text: '开始巡逻',
              type: FgBtnType.Primary,
              onTap: () => { this.doStartPatrol() }
            })
          }
        }

        FgButton({
          text: '查看地图导航',
          onTap: () => { router.pushUrl({ url: 'pages/ScreenMapNav' }) }
        })
      }
      .width('100%')
      .margin({ top: 10 })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  /** 路线预览：地图为底，叠加途经点圆点和有向箭头 */
  @Builder
  routePreview() {
    Stack() {
      if (this.mapUrl.length > 0) {
        Image(this.mapUrl)
          .width('100%')
          .height(120)
          .objectFit(ImageFit.Contain)
          .borderRadius(6)
          .brightness(0.7)
      }

      this.routeDots()
    }
    .width('100%')
    .height(120)
    .borderRadius(8)
    .clip(true)
    .backgroundColor('#0a1622')
    .margin({ top: 6, bottom: 10 })
  }

  @Builder
  routeDots() {
    ForEach(this.routePixels(), (it: MapPixel, idx: number) => {
      this.waypointDot(it.x, it.y, idx + 1, idx === this.customPoints.length - 1)
      if (it.nextX >= 0 && it.nextY >= 0) {
        this.routeArrow(it.x, it.y, it.nextX, it.nextY)
      }
    }, (it: MapPixel) => `${it.x}_${it.y}`)
  }

  @Builder
  waypointDot(x: number, y: number, num: number, isLast: boolean) {
    Row() {
      Column() {
        Text(`${num}`)
          .fontSize(9)
          .fontColor('#fff')
          .fontWeight(FontWeight.Bold)
      }
      .width(18)
      .height(18)
      .borderRadius(9)
      .backgroundColor(isLast ? FG.orange : FG.cyan)
      .justifyContent(FlexAlign.Center)
      .alignItems(HorizontalAlign.Center)
    }
    .width(18)
    .height(18)
    .position({ x: x - 9, y: y - 9 })
  }

  @Builder
  routeArrow(x1: number, y1: number, x2: number, y2: number) {
    // 箭头线段
    Line()
      .width(Math.sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1)))
      .height(1.5)
      .stroke('rgba(255, 151, 72, 0.7)').strokeWidth(2)
      .position({ x: x1, y: y1 - 1 })
      .rotate({
        angle: Math.atan2(y2 - y1, x2 - x1) * (180 / Math.PI)
      })
      
    // 箭头尖端三角
    Line()
      .width(8)
      .height(0)
      .stroke('rgba(255, 151, 72, 0.9)').strokeWidth(2)
      .position({ x: x2 - 4, y: y2 - 2 })
      .rotate({
        angle: Math.atan2(y2 - y1, x2 - x1) * (180 / Math.PI) - 30
      })
          Line()
      .width(8)
      .height(0)
      .stroke('rgba(255, 151, 72, 0.9)').strokeWidth(2)
      .position({ x: x2 - 4, y: y2 })
      .rotate({
        angle: Math.atan2(y2 - y1, x2 - x1) * (180 / Math.PI) + 30
      })
        }

  // ---- 编辑弹窗 ----
  @Builder
  editDialog() {
    Column() {
      Column() {
        Text('编辑预设点')
          .fontSize(16)
          .fontWeight(FontWeight.Bold)
          .fontColor(FG.text)
          .margin({ bottom: 12 })

        TextInput({ text: this.editLabel, placeholder: '名称' })
          .fontSize(FG.bodySize).fontColor(FG.text)
          .height(40).width('100%')
          .padding({ left: 12, right: 12 })
          .borderRadius(8).border({ width: 1, color: FG.inputBorder })
          .backgroundColor(FG.inputBg)
          .onChange((v: string) => { this.editLabel = v })
          .margin({ bottom: 8 })

        Row({ space: 8 }) {
          TextInput({ text: this.editX, placeholder: 'X 坐标' })
            .fontSize(FG.bodySize).fontColor(FG.text)
            .height(40).width('100%')
            .padding({ left: 12, right: 12 })
            .borderRadius(8).border({ width: 1, color: FG.inputBorder })
            .backgroundColor(FG.inputBg)
            .onChange((v: string) => { this.editX = v })
          TextInput({ text: this.editY, placeholder: 'Y 坐标' })
            .fontSize(FG.bodySize).fontColor(FG.text)
            .height(40).width('100%')
            .padding({ left: 12, right: 12 })
            .borderRadius(8).border({ width: 1, color: FG.inputBorder })
            .backgroundColor(FG.inputBg)
            .onChange((v: string) => { this.editY = v })
        }
        .width('100%')
        .margin({ bottom: 16 })

        Row() {
          Row() {
            Text('取消').fontSize(FG.bodySize).fontWeight(FontWeight.Bold).fontColor(FG.text)
          }
          .layoutWeight(1).height(42).justifyContent(FlexAlign.Center)
          .borderRadius(FG.btnRadius).backgroundColor(FG.btnDefault)
          .margin({ right: 5 })
          .onClick(() => { this.editing = false })

          Row() {
            Text('保存').fontSize(FG.bodySize).fontWeight(FontWeight.Bold).fontColor('#10151d')
          }
          .layoutWeight(1).height(42).justifyContent(FlexAlign.Center)
          .borderRadius(FG.btnRadius).backgroundColor(FG.orange)
          .margin({ left: 5 })
          .onClick(() => { this.saveEdit() })
        }
        .width('100%')
      }
      .width(300).padding(20)
      .borderRadius(FG.cardRadius)
      .border({ width: 1, color: FG.line })
      .backgroundColor('#101927')
    }
    .width('100%').height('100%')
    .justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
    .backgroundColor('rgba(0, 0, 0, 0.5)')
  }

  // ---- 坐标换算 ----

  /** 返回所有途经点的像素坐标（含下一点的箭头终点），供 routeDots @Builder 直接遍历 */
  private routePixels(): MapPixel[] {
    const result: MapPixel[] = []
    for (let i = 0; i < this.customPoints.length; i++) {
      const p: LinkedWaypoint = this.customPoints[i]
      const pos: PixelPoint = this.worldToPixelSafe(p.x, p.y)
      const item: MapPixel = { x: pos.x, y: pos.y, nextX: -1, nextY: -1 }
      if (i < this.customPoints.length - 1) {
        const n: PixelPoint = this.worldToPixelSafe(this.customPoints[i + 1].x, this.customPoints[i + 1].y)
        item.nextX = n.x
        item.nextY = n.y
      }
      result.push(item)
    }
    return result
  }

  private worldToPixelSafe(wx: number, wy: number): PixelPoint {
    const p: PixelPoint | null = this.worldToPixel(wx, wy)
    return p !== null ? p : { x: 0, y: 0 }
  }

  private worldToPixel(wx: number, wy: number): PixelPoint | null {
    if (this.mapMeta === null) return null
    const m = this.mapMeta
    const areaH: number = 120 // 预览区高度
    // 图片按宽充满，按 aspect 居中：实际图片高度 = 宽 / w * h
    const px: number = (wx - m.origin[0]) / m.resolution
    const pyBot: number = (wy - m.origin[1]) / m.resolution // 从底部算的像素行
    const imgX: number = (px / m.width) * 300 // 约等于页面可用宽
    const imgH: number = (m.height / m.width) * 300 // 按比例算出图片显示高度
    const imgY: number = areaH - (pyBot / m.height) * imgH - (areaH - imgH) / 2
    return { x: imgX, y: imgY }
  }

  /** 长按预设点 → 打开编辑弹窗 */
  private openEdit(idx: number): void {
    const p: PresetPoint = this.presetPoints[idx]
    this.editIdx = idx
    this.editLabel = p.label
    this.editX = p.x.toFixed(2)
    this.editY = p.y.toFixed(2)
    this.editing = true
  }

  private saveEdit(): void {
    const nx: number = parseFloat(this.editX)
    const ny: number = parseFloat(this.editY)
    if (isNaN(nx) || isNaN(ny)) {
      promptAction.showToast({ message: '坐标格式无效' })
      return
    }
    if (this.editIdx < 0) {
      this.editing = false
      return
    }
    // 找到被编辑的点（按当前显示的 presetPoints 定位）
    const target: PresetPoint = this.presetPoints[this.editIdx]
    // 只允许编辑静态预设点（source==static），车端路由点不改
    if (target.source !== 'static') {
      promptAction.showToast({ message: '车端路线点不可编辑' })
      this.editing = false
      return
    }
    const newLabel: string = this.editLabel.length > 0 ? this.editLabel : target.label

    // 写入可编辑基准 editablePresets（按 label 匹配原始点）
    const base: PresetPoint[] = []
    for (let i = 0; i < this.editablePresets.length; i++) {
      const ep: PresetPoint = this.editablePresets[i]
      if (ep.label === target.label && Math.abs(ep.x - target.x) < 0.01 && Math.abs(ep.y - target.y) < 0.01) {
        base.push({ x: nx, y: ny, label: newLabel, source: 'static' })
      } else {
        base.push(ep)
      }
    }
    this.editablePresets = base

    // 同步更新当前显示列表
    const disp: PresetPoint[] = []
    for (let i = 0; i < this.presetPoints.length; i++) {
      if (i === this.editIdx) {
        disp.push({ x: nx, y: ny, label: newLabel, source: 'static' })
      } else {
        disp.push(this.presetPoints[i])
      }
    }
    this.presetPoints = disp

    this.editing = false
    promptAction.showToast({ message: '预设点已更新（本次会话有效）' })
  }

  /** 自选：添加预设点到路线 */
  private addCustomPoint(p: PresetPoint): void {
    const lp: LinkedWaypoint = { x: p.x, y: p.y, label: p.label }
    this.customPoints = this.customPoints.concat([lp])
    this.selectedRoute = ''  // 自选模式下清除已保存路线的选中态
  }

  /** 自选：移除途经点 */
  private removeCustomPoint(idx: number): void {
    const arr: LinkedWaypoint[] = []
    for (let i = 0; i < this.customPoints.length; i++) {
      if (i !== idx) {
        arr.push(this.customPoints[i])
      }
    }
    this.customPoints = arr
  }

  /** 自选：应用当前路线到车端 */
  private async applyCustomRoute(): Promise<void> {
    if (this.customPoints.length === 0) {
      promptAction.showToast({ message: '请先添加途经点' })
      return
    }
    this.busy = true
    const points: Waypoint[] = []
    for (let i = 0; i < this.customPoints.length; i++) {
      points.push({ x: this.customPoints[i].x, y: this.customPoints[i].y })
    }
    const ok: boolean = await restApiClient.setPatrolRoute(points)
    this.busy = false
    this.refreshAll()
    promptAction.showToast({ message: ok ? '自选路线已设置' : '路线设置失败' })
  }

  /** 点击配送方案 → 设为当前路线 */
  private async selectRoute(name: string): Promise<void> {
    this.selectedRoute = name
    this.customPoints = new Array<LinkedWaypoint>()  // 清除自选路线
    this.busy = true
    const detail: PatrolRoute | null = await restApiClient.getPatrolRouteDetail(name)
    if (detail !== null && detail.success) {
      const ok: boolean = await restApiClient.setPatrolRoute(detail.points)
      if (ok) {
        promptAction.showToast({ message: `已选中方案: ${name}` })
      } else {
        promptAction.showToast({ message: '路线设置失败' })
      }
    } else {
      promptAction.showToast({ message: '读取方案详情失败' })
    }
    this.busy = false
    this.refreshAll()
  }

  private async doStartPatrol(): Promise<void> {
    const ok: boolean = await restApiClient.startPatrol()
    this.refreshAll()
    promptAction.showToast({ message: ok ? '已开始巡逻' : '巡逻启动失败' })
  }

  private async doStopPatrol(): Promise<void> {
    const ok: boolean = await restApiClient.stopPatrol()
    this.refreshAll()
    promptAction.showToast({ message: ok ? '已停止巡逻' : '停止巡逻失败' })
  }

  private patrolPercent(): number {
    if (this.patrolStatus === null || this.patrolRoute === null
      || this.patrolRoute.point_count <= 0) return 0
    const wp: number = parseInt(this.patrolStatus.status.replace('navigating_waypoint_', '')) || 0
    return Math.round(Math.min(wp / this.patrolRoute.point_count * 100, 100))
  }

  private async startStack(): Promise<void> {
    const ok: boolean = await restApiClient.startStack()
    this.refreshAll()
    promptAction.showToast({ message: ok ? '导航栈启动中（约 15 秒）' : '启动失败' })
  }
}
