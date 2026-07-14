/**
 * 导航 API 数据模型（/api/nav/）
 * 对应《小车端功能对接文档》2.4 节
 */

/** GET /api/nav/stack/status */
export interface NavStackStatus {
  container: string
  container_running: boolean
  patrol_ready: boolean
  stack_ready: boolean
  starting: boolean
  stopping: boolean
  ros_domain_id: string
  stack_message: string
  log_tail: string
  hint: string
}

/** GET /api/nav/patrol/status */
export interface PatrolStatus {
  status: string               // idle / ready / navigating_waypoint_N
  patrol_active: boolean
  point_count: number
  loop: boolean
}

/** GET /api/nav/patrol/route */
export interface PatrolRoute {
  success: boolean
  point_count: number
  patrol_active: boolean
  loop: boolean
  points: Waypoint[]
}

/** 单个巡逻点 */
export interface Waypoint {
  x: number
  y: number
}

/** 带标签的巡逻点（前端 UI 用） */
export interface LinkedWaypoint {
  x: number
  y: number
  label: string
}

/** 路线名称项 */
export interface RouteNameItem {
  name: string
}

/** GET /api/nav/map */
export interface NavMapMeta {
  map: string
  width: number
  height: number
  resolution: number
  origin: number[]
}
