/**
 * 巡逻/配送 预设点位配置
 * ScreenDelivery 使用，可在此文件中增删改预设巡检点。
 *
 * 数据来源（两路合并去重）：
 * 1. 本文件的 PRESET_POINTS 静态配置（label 为友好名称）
 * 2. 运行时从车端 GET /api/nav/patrol/routes 下每条路线的途经点自动提取
 *    （label 为 "路线名·途经点N"）
 */
import { Waypoint } from '../tcp/NavModels'

/** 一个预设巡检点的坐标 + 友好名称 */
export interface PresetPoint {
  x: number
  y: number
  label: string
  /** 来源：'static' = 本文件配置，'route' = 从车端路线提取 */
  source: string
}

export interface PixelPoint {
  x: number
  y: number
}

export interface MapPixel {
  x: number
  y: number
  nextX: number
  nextY: number
}

/* ---- 静态预设点（可根据实际地图场景自由修改坐标和名称）---- */
export const PRESET_POINTS: PresetPoint[] = [
  { x: -1.5, y: 3.2, label: '配电柜 A', source: 'static' },
  { x: 2.0, y: -1.0, label: '配电柜 B', source: 'static' },
  { x: -3.0, y: -0.5, label: '仓储通道', source: 'static' },
  { x: 1.5, y: 2.0, label: '消防器材点', source: 'static' },
  { x: 0.0, y: 0.0, label: '充电待命点', source: 'static' },
  { x: -2.0, y: 1.5, label: '应急物资点 D', source: 'static' },
]

/**
 * 从一组途经点 + 路线名生成预设点列表
 * @param points  路线途经点数组
 * @param routeName  路线名（如 "campus"）
 */
export function pointsToPresets(points: Waypoint[], routeName: string): PresetPoint[] {
  const result: PresetPoint[] = []
  for (let i = 0; i < points.length; i++) {
    result.push({
      x: points[i].x,
      y: points[i].y,
      label: `${routeName}·途经点${i + 1}`,
      source: 'route'
    })
  }
  return result
}

/**
 * 合并 + 去重（相近坐标视为同一点，阈值 0.3 米）
 * 先放静态配置，再放路线提取的，保证静态点优先保留。
 */
export function mergePresets(...lists: PresetPoint[][]): PresetPoint[] {
  const result: PresetPoint[] = []
  const threshold: number = 0.3
  const addIfNew = (p: PresetPoint): void => {
    for (let i = 0; i < result.length; i++) {
      const dx: number = result[i].x - p.x
      const dy: number = result[i].y - p.y
      if (Math.sqrt(dx * dx + dy * dy) < threshold) {
        return  // 已存在相近点，跳过
      }
    }
    result.push(p)
  }

  for (let i = 0; i < lists.length; i++) {
    for (let j = 0; j < lists[i].length; j++) {
      addIfNew(lists[i][j])
    }
  }
  return result
}
