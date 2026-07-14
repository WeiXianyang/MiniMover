/**
 * 车端 / 云端 API 数据模型
 * 对应《小车端功能对接文档》与《云端API接口文档（前端对接）》。
 */

/* ======================= 小车 REST (:5000) ======================= */

/** GPS 坐标 */
export interface GpsData {
  lat: number
  lon: number
}

/** GET /api/sensors 及 /api/status.sensors */
export interface SensorData {
  temperature: number
  humidity: number
  smoke: number
  pm25: number
  pressure: number
  light: number
  co2: number
  gps: GpsData
}

/** GET /api/status.data */
export interface CarStatus {
  sensors: SensorData
  battery: number
  ip: string
}

/** GET /api/map.data */
export interface MapMeta {
  width: number
  height: number
  resolution: number
  origin: number[]
}

/** GET /api/audio/record/status.data */
export interface RecordStatus {
  status: string   // idle | recording | done
  elapsed: number
}

/** GET /api/camera.data */
export interface CameraInfo {
  mjpeg: string
  ros_stream: string
  snapshot: string
}
