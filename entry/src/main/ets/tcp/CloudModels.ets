/**
 * 云平台告警 API 数据模型（:8000）
 * 对应《云端API接口文档（前端对接）》http://8.140.28.233:8000
 */

/** 告警记录（列表项 / 详情共用） */
export interface FireAlarm {
  id: number
  event_id: string
  alarm_type: string        // confirmed_fire | suspected_smoke | ai_unavailable
  occurred_at: string
  reason: string
  confidence: number
  evidence_url: string
  detection_classes: string
  max_confidence: number
  local_detection_gone: boolean
  car_id: string
  received_at: string
}

/** 告警列表分页响应 data */
export interface FireAlarmPage {
  total: number
  page: number
  size: number
  items: FireAlarm[]
}
