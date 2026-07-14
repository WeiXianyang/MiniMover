/**
 * REST API 客户端（单例）
 * 通过 HTTP/JSON 与小车 Flask api_server.py（端口 5000）通信。
 * 所有响应统一格式：{"code": 0, "msg": "ok", "data": {...}}，code=0 为成功。
 */
import http from '@ohos.net.http'
import { CarStatus, SensorData, MapMeta, RecordStatus } from './CarModels'
import { NavStackStatus, PatrolStatus, PatrolRoute, NavMapMeta, Waypoint, RouteNameItem } from './NavModels'

/** 通用响应包络 */
interface ApiEnvelope {
  code: number
  msg: string
  data?: object
}

class RestApiClient {
  private static instance: RestApiClient | undefined = undefined
  private baseUrl: string = ''

  static getInstance(): RestApiClient {
    if (!RestApiClient.instance) {
      RestApiClient.instance = new RestApiClient()
    }
    return RestApiClient.instance
  }

  initConnection(ip: string, port: number): void {
    this.baseUrl = `http://${ip}:${port}`
  }

  getBaseUrl(): string {
    return this.baseUrl
  }

  /* ---------------- 内部通用请求 ---------------- */

  /** 发起请求并解析 {code,msg,data} 包络，返回 data（失败返回 null） */
  private requestJson(path: string, method: http.RequestMethod, body?: string): Promise<object | null> {
    return new Promise<object | null>((resolve: (value: object | null) => void) => {
      const req = http.createHttp()
      const options: http.HttpRequestOptions = {
        method: method,
        header: { 'Content-Type': 'application/json' },
        connectTimeout: 5000,
        readTimeout: 5000
      }
      if (body !== undefined) {
        options.extraData = body
      }
      req.request(`${this.baseUrl}${path}`, options).then((resp: http.HttpResponse) => {
        try {
          const env: ApiEnvelope = JSON.parse(resp.result as string) as ApiEnvelope
          if (env.code === 0) {
            resolve(env.data !== undefined ? env.data : new Object())
          } else {
            console.error(`[RestApiClient] ${path} code=${env.code} msg=${env.msg}`)
            resolve(null)
          }
        } catch (e) {
          console.error(`[RestApiClient] ${path} parse error: ${JSON.stringify(e)}`)
          resolve(null)
        }
      }).catch((err: Error) => {
        console.error(`[RestApiClient] ${path} failed: ${JSON.stringify(err)}`)
        resolve(null)
      }).finally(() => {
        req.destroy()
      })
    })
  }

  /* ---------------- 系统状态 ---------------- */

  /** GET /api/health — 健康检查（仅判断可达 + code=0） */
  checkHealth(): Promise<boolean> {
    return new Promise<boolean>((resolve: (value: boolean) => void) => {
      const req = http.createHttp()
      req.request(`${this.baseUrl}/api/health`, {
        method: http.RequestMethod.GET,
        connectTimeout: 5000,
        readTimeout: 5000
      }).then((resp: http.HttpResponse) => {
        try {
          const env: ApiEnvelope = JSON.parse(resp.result as string) as ApiEnvelope
          resolve(env.code === 0)
        } catch (e) {
          resolve(false)
        }
      }).catch((err: Error) => {
        console.error(`[RestApiClient] checkHealth failed: ${JSON.stringify(err)}`)
        resolve(false)
      }).finally(() => {
        req.destroy()
      })
    })
  }

  /** GET /api/status — 全状态快照（传感器 + 电量 + IP） */
  async getStatus(): Promise<CarStatus | null> {
    const data: object | null = await this.requestJson('/api/status', http.RequestMethod.GET)
    return data === null ? null : data as CarStatus
  }

  /** GET /api/sensors — 仅传感器数据 */
  async getSensors(): Promise<SensorData | null> {
    const data: object | null = await this.requestJson('/api/sensors', http.RequestMethod.GET)
    return data === null ? null : data as SensorData
  }

  /* ---------------- 底盘控制 ---------------- */

  /**
   * POST /api/move — 控制移动（带持续时长，到时自动停止）
   * cmd: forward/backward/left/right/left_shift/right_shift/stop
   */
  sendMove(cmd: string, speed: number, duration: number): Promise<boolean> {
    const body: string = JSON.stringify({ cmd: cmd, speed: speed, duration: duration })
    return this.requestJson('/api/move', http.RequestMethod.POST, body)
      .then((data: object | null) => data !== null)
  }

  /** POST /api/move — 持续移动（不带 duration，用于摇杆轮询） */
  sendMoveContinuous(cmd: string, speed: number): Promise<boolean> {
    const body: string = JSON.stringify({ cmd: cmd, speed: speed })
    return this.requestJson('/api/move', http.RequestMethod.POST, body)
      .then((data: object | null) => data !== null)
  }

  /* ---------------- 导航 / 定点配送（/api/nav/） ---------------- */

  /** GET /api/nav/map — 导航地图元数据 */
  async getNavMapMeta(): Promise<NavMapMeta | null> {
    const data: object | null = await this.requestJson('/api/nav/map', http.RequestMethod.GET)
    return data === null ? null : data as NavMapMeta
  }

  /** 导航地图图片 URL */
  getNavMapImageUrl(): string {
    return `${this.baseUrl}/api/nav/map/image`
  }

  /** POST /api/nav/coord/pixel_to_map — 像素→世界坐标转换 */
  async pixelToWorld(sx: number, sy: number, dw: number, dh: number): Promise<Waypoint | null> {
    const body: string = JSON.stringify({ screen_x: sx, screen_y: sy, display_width: dw, display_height: dh })
    const data: object | null = await this.requestJson('/api/nav/coord/pixel_to_map', http.RequestMethod.POST, body)
    return data === null ? null : data as Waypoint
  }

  /** GET /api/nav/stack/status — 导航栈状态 */
  async getStackStatus(): Promise<NavStackStatus | null> {
    const data: object | null = await this.requestJson('/api/nav/stack/status', http.RequestMethod.GET)
    return data === null ? null : data as NavStackStatus
  }

  /** POST /api/nav/stack/start — 启动导航栈 */
  startStack(): Promise<boolean> {
    return this.requestJson('/api/nav/stack/start', http.RequestMethod.POST, '{}')
      .then((data: object | null) => data !== null)
  }

  /** POST /api/nav/stack/stop — 关闭导航栈 */
  stopStack(): Promise<boolean> {
    return this.requestJson('/api/nav/stack/stop', http.RequestMethod.POST, '{}')
      .then((data: object | null) => data !== null)
  }

  /** POST /api/nav/initial_pose — 设置初始位姿 */
  sendInitialPose(x: number, y: number, yaw: number): Promise<boolean> {
    const body: string = JSON.stringify({ x: x, y: y, yaw: yaw })
    return this.requestJson('/api/nav/initial_pose', http.RequestMethod.POST, body)
      .then((data: object | null) => data !== null)
  }

  /** GET /api/nav/patrol/route — 获取当前巡逻路线 */
  async getPatrolRoute(): Promise<PatrolRoute | null> {
    const data: object | null = await this.requestJson('/api/nav/patrol/route', http.RequestMethod.GET)
    return data === null ? null : data as PatrolRoute
  }

  /** POST /api/nav/patrol/route — 设置巡逻路线 */
  setPatrolRoute(points: Waypoint[]): Promise<boolean> {
    const body: string = JSON.stringify({ points: points })
    return this.requestJson('/api/nav/patrol/route', http.RequestMethod.POST, body)
      .then((data: object | null) => data !== null)
  }

  /** POST /api/nav/patrol/start — 开始巡逻 */
  startPatrol(): Promise<boolean> {
    return this.requestJson('/api/nav/patrol/start', http.RequestMethod.POST, '{}')
      .then((data: object | null) => data !== null)
  }

  /** POST /api/nav/patrol/stop — 停止巡逻 */
  stopPatrol(): Promise<boolean> {
    return this.requestJson('/api/nav/patrol/stop', http.RequestMethod.POST, '{}')
      .then((data: object | null) => data !== null)
  }

  /** POST /api/nav/patrol/clear — 清除巡逻路线 */
  clearPatrol(): Promise<boolean> {
    return this.requestJson('/api/nav/patrol/clear', http.RequestMethod.POST, '{}')
      .then((data: object | null) => data !== null)
  }

  /** GET /api/nav/patrol/status — 巡逻运行状态 */
  async getPatrolStatus(): Promise<PatrolStatus | null> {
    const data: object | null = await this.requestJson('/api/nav/patrol/status', http.RequestMethod.GET)
    return data === null ? null : data as PatrolStatus
  }

  /** POST /api/nav/patrol/loop — 设置巡逻循环模式 */
  setPatrolLoop(loop: boolean): Promise<boolean> {
    const body: string = JSON.stringify({ loop: loop })
    return this.requestJson('/api/nav/patrol/loop', http.RequestMethod.POST, body)
      .then((data: object | null) => data !== null)
  }

  /** GET /api/nav/patrol/routes — 已保存路线名称列表 */
  async getPatrolRoutes(): Promise<RouteNameItem[]> {
    const data: object | null = await this.requestJson('/api/nav/patrol/routes', http.RequestMethod.GET)
    if (data === null) return []
    // API 返回 {code:0, data: [{name:"campus"},{name:"warehouse"}]}
    return data as RouteNameItem[]
  }

  /** GET /api/nav/patrol/routes/<name> — 获取已保存路线详情（含 points） */
  async getPatrolRouteDetail(name: string): Promise<PatrolRoute | null> {
    const data: object | null = await this.requestJson(`/api/nav/patrol/routes/${name}`, http.RequestMethod.GET)
    return data === null ? null : data as PatrolRoute
  }

  // ---- 兼容旧版端点（/api/map, /api/map_image, /api/navigate）----
  /** GET /api/map — 地图元数据（兼容旧版） */
  async getMapMeta(): Promise<MapMeta | null> {
    const data: object | null = await this.requestJson('/api/map', http.RequestMethod.GET)
    return data === null ? null : data as MapMeta
  }

  /** 地图图片 URL（兼容旧版） */
  getMapImageUrl(): string {
    return `${this.baseUrl}/api/map_image`
  }

  /** POST /api/navigate — 发送导航目标点（兼容旧版） */
  sendNavigate(x: number, y: number, theta: number): Promise<boolean> {
    const body: string = JSON.stringify({ x: x, y: y, theta: theta })
    return this.requestJson('/api/navigate', http.RequestMethod.POST, body)
      .then((data: object | null) => data !== null)
  }

  /* ---------------- 音频服务 ---------------- */

  /** POST /api/audio/say — TTS 文本转语音 */
  sendTts(text: string, lang: string): Promise<boolean> {
    const body: string = JSON.stringify({ text: text, lang: lang })
    return this.requestJson('/api/audio/say', http.RequestMethod.POST, body)
      .then((data: object | null) => data !== null)
  }

  /** POST /api/audio/stop — 停止播放 */
  stopAudio(): Promise<boolean> {
    return this.requestJson('/api/audio/stop', http.RequestMethod.POST, '{}')
      .then((data: object | null) => data !== null)
  }

  /** POST /api/audio/record/start — 开始录音（duration=0 为手动停止模式） */
  startRecord(duration: number): Promise<boolean> {
    const body: string = JSON.stringify({ duration: duration })
    return this.requestJson('/api/audio/record/start', http.RequestMethod.POST, body)
      .then((data: object | null) => data !== null)
  }

  /** GET /api/audio/record/status — 查询录音状态 */
  async getRecordStatus(): Promise<RecordStatus | null> {
    const data: object | null = await this.requestJson('/api/audio/record/status', http.RequestMethod.GET)
    return data === null ? null : data as RecordStatus
  }

  /** POST /api/audio/record/stop — 停止录音 */
  stopRecord(): Promise<boolean> {
    return this.requestJson('/api/audio/record/stop', http.RequestMethod.POST, '{}')
      .then((data: object | null) => data !== null)
  }

  /** 视频流 URL（MJPEG，直接给 Web/Image 组件用） */
  getVideoFeedUrl(): string {
    return `${this.baseUrl}/video_feed`
  }
}

export const restApiClient: RestApiClient = RestApiClient.getInstance()
