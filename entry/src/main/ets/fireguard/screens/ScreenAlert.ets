/**
 * S04 告警详情
 * 对接云平台 /api/v1/fire-alarms，展示最新一条火情告警。
 * 无数据时显示空态；"远程接管"导航至横屏手动接管页。
 */
import router from '@ohos.router'
import { FG } from '../Theme'
import { FgPageHead, FgCard, FgRow, FgRecommend, FgButton, FgStatus, FgBtnType } from '../Widgets'
import { FgTab } from '../Tabs'
import { cloudApiClient } from '../../tcp/CloudApiClient'
import { FireAlarm, FireAlarmPage } from '../../tcp/CloudModels'

@Component
export struct ScreenAlert {
  gotoTab: (tab: FgTab) => void = () => {}

  /** 最新告警，null 表示无 */
  @State alarm: FireAlarm | null = null
  /** 是否加载中 */
  @State loading: boolean = true

  aboutToAppear(): void {
    this.loadLatest()
  }

  private async loadLatest(): Promise<void> {
    this.loading = true
    const pageData: FireAlarmPage | null = await cloudApiClient.getAlarms(1, 1)
    if (pageData !== null && pageData.items.length > 0) {
      this.alarm = pageData.items[0]
    } else {
      this.alarm = null
    }
    this.loading = false
  }

  /** 告警类型中文 */
  private typeLabel(t: string): string {
    if (t === 'confirmed_fire') return '确认明火'
    if (t === 'suspected_smoke') return '疑似烟雾'
    if (t === 'ai_unavailable') return 'AI 复核失效'
    return t
  }

  /** 告警等级药丸状态 */
  private typeStatus(t: string): FgStatus {
    if (t === 'confirmed_fire') return FgStatus.Red
    if (t === 'suspected_smoke') return FgStatus.Orange
    return FgStatus.Green
  }

  /** ISO 时间截断到分钟（容错 null） */
  private fmtTime(iso: string): string {
    if (iso === null || iso === undefined || iso.length === 0) {
      return '--'
    }
    if (iso.length >= 16) {
      return iso.substring(0, 16).replace('T', ' ')
    }
    return iso
  }

  /** 安全取字符串，null/undefined 返回占位 */
  private safeStr(s: string): string {
    return (s !== null && s !== undefined && s.length > 0) ? s : '--'
  }

  build() {
    Column() {
      FgPageHead({
        title: '告警详情',
        subtitle: this.alarm !== null ? `${this.safeStr(this.alarm.car_id)} · ${this.typeLabel(this.alarm.alarm_type)}` : '云平台火情告警',
        pillText: this.alarm !== null ? this.typeLabel(this.alarm.alarm_type) : (this.loading ? '加载中' : '暂无告警'),
        pillStatus: this.alarm !== null ? this.typeStatus(this.alarm.alarm_type) : FgStatus.Green
      })

      if (this.alarm !== null) {
        this.buildAlarm(this.alarm)
      } else {
        this.buildEmpty()
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  buildAlarm(a: FireAlarm) {
    // 告警证据图区域：有 evidence_url 显示图片，无图/加载失败回退红色光晕
    Stack() {
      if (a.evidence_url !== null && a.evidence_url !== undefined && a.evidence_url.length > 0) {
        Image(a.evidence_url)
          .width('100%')
          .height('100%')
          .objectFit(ImageFit.Cover)
          .borderRadius(FG.cardRadius)
          .alt($r('app.media.triangle_alert'))
      } else {
        Text('无证据图片')
          .fontSize(FG.bodySize)
          .fontColor(FG.muted)
      }
    }
    .width('100%')
    .height(172)
    .margin({ bottom: 14 })
    .borderRadius(FG.cardRadius)
    .clip(true)
    .border({ width: 1, color: 'rgba(255, 101, 112, 0.55)' })
    .backgroundColor('#162235')
    .radialGradient({
      center: ['54%', '38%'],
      radius: 44,
      colors: [['rgba(255, 101, 112, 0.26)', 0], ['rgba(255, 101, 112, 0)', 1]]
    })

    FgCard() {
      FgRow({ label: '识别类型', value: this.typeLabel(a.alarm_type) })
      FgRow({
        label: '命中类别',
        value: (a.detection_classes !== null && a.detection_classes !== undefined && a.detection_classes.length > 0)
          ? a.detection_classes : '--'
      })
      FgRow({
        label: '置信度',
        value: (a.confidence !== null && a.confidence !== undefined) ? `${Math.round(a.confidence * 100)}%` : '--'
      })
      FgRow({ label: '发生时间', value: this.fmtTime(a.occurred_at) })
      FgRow({ label: '车辆', value: this.safeStr(a.car_id), showBorder: false })
    }

    FgRecommend({
      label: '处置建议',
      title: (a.reason !== null && a.reason !== undefined && a.reason.length > 0)
        ? a.reason : '请派发定点配送并通知现场人员确认。'
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

  @Builder
  buildEmpty() {
    Column() {
      FgRecommend({
        label: '告警状态',
        title: this.loading ? '正在加载云平台告警…' : '当前无火情告警',
        desc: this.loading ? '' : '云平台暂无上报记录，或未连接到云平台。'
      })

      FgButton({
        text: '刷新',
        type: FgBtnType.Primary,
        onTap: () => { this.loadLatest() }
      })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }
}
