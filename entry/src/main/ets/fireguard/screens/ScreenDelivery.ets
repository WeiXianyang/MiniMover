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
import { PatrolStatus, PatrolRoute, NavStackStatus, Waypoint, LinkedWaypoint, RouteNameItem } from '../../tcp/NavModels'

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

  /** 预设固定巡检点（坐标按实际地图调整，当前用示例值） */
  private presetPoints: LinkedWaypoint[] = [
    { x: -1.5, y: 3.2, label: '配电柜 A' },
    { x: 2.0, y: -1.0, label: '配电柜 B' },
    { x: -3.0, y: -0.5, label: '仓储通道' },
    { x: 1.5, y: 2.0, label: '消防器材点' },
    { x: 0.0, y: 0.0, label: '充电待命点' },
    { x: -2.0, y: 1.5, label: '应急物资点 D' },
  ]

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
    const ps: PatrolStatus | null = await restApiClient.getPatrolStatus()
    const pr: PatrolRoute | null = await restApiClient.getPatrolRoute()
    const ss: NavStackStatus | null = await restApiClient.getStackStatus()
    const sr: RouteNameItem[] = await restApiClient.getPatrolRoutes()
    this.patrolStatus = ps
    this.patrolRoute = pr
    this.stackStatus = ss
    this.savedRoutes = sr
    this.loading = false
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
        ForEach(this.presetPoints, (p: LinkedWaypoint) => {
          GridItem() {
            Column() {
              Text(p.label)
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
            .backgroundColor(FG.btnDefault)
            .onClick(() => { this.addCustomPoint(p) })
          }
        }, (p: LinkedWaypoint) => p.label)
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

  /** 自选：添加预设点到路线 */
  private addCustomPoint(p: LinkedWaypoint): void {
    this.customPoints = this.customPoints.concat([p])
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
