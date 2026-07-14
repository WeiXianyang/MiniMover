/**
 * 云平台告警 API 客户端（单例）
 * 对接《云端API接口文档（前端对接）》，默认地址 http://8.140.28.233:8000。
 * 响应格式统一 {"code":0,"msg":"ok","data":{...}}，code=0 为成功。
 * 鉴权：若配置了 token 则带 Authorization: Bearer <token>，未开启鉴权时留空即可。
 */
import http from '@ohos.net.http'
import { FireAlarmPage, FireAlarm } from './CloudModels'

interface CloudEnvelope {
  code: number
  msg: string
  data?: object
}

class CloudApiClient {
  private static instance: CloudApiClient | undefined = undefined
  private baseUrl: string = 'http://8.140.28.233:8000'
  private token: string = ''

  static getInstance(): CloudApiClient {
    if (!CloudApiClient.instance) {
      CloudApiClient.instance = new CloudApiClient()
    }
    return CloudApiClient.instance
  }

  /** 配置云平台地址与鉴权 token（可选） */
  configure(baseUrl: string, token: string): void {
    if (baseUrl.length > 0) {
      this.baseUrl = baseUrl
    }
    this.token = token
  }

  private buildHeader(): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
    if (this.token.length > 0) {
      h['Authorization'] = `Bearer ${this.token}`
    }
    return h
  }

  private requestJson(path: string): Promise<object | null> {
    return new Promise<object | null>((resolve: (value: object | null) => void) => {
      const req = http.createHttp()
      req.request(`${this.baseUrl}${path}`, {
        method: http.RequestMethod.GET,
        header: this.buildHeader(),
        connectTimeout: 8000,
        readTimeout: 8000
      }).then((resp: http.HttpResponse) => {
        try {
          const env: CloudEnvelope = JSON.parse(resp.result as string) as CloudEnvelope
          if (env.code === 0) {
            resolve(env.data !== undefined ? env.data : new Object())
          } else {
            console.error(`[CloudApiClient] ${path} code=${env.code} msg=${env.msg}`)
            resolve(null)
          }
        } catch (e) {
          console.error(`[CloudApiClient] ${path} parse error: ${JSON.stringify(e)}`)
          resolve(null)
        }
      }).catch((err: Error) => {
        console.error(`[CloudApiClient] ${path} failed: ${JSON.stringify(err)}`)
        resolve(null)
      }).finally(() => {
        req.destroy()
      })
    })
  }

  /** GET /api/v1/fire-alarms — 告警列表（分页） */
  async getAlarms(page: number, size: number): Promise<FireAlarmPage | null> {
    const data: object | null = await this.requestJson(`/api/v1/fire-alarms?page=${page}&size=${size}`)
    return data === null ? null : data as FireAlarmPage
  }

  /** GET /api/v1/fire-alarms/{id} — 告警详情 */
  async getAlarmDetail(id: number): Promise<FireAlarm | null> {
    const data: object | null = await this.requestJson(`/api/v1/fire-alarms/${id}`)
    return data === null ? null : data as FireAlarm
  }
}

export const cloudApiClient: CloudApiClient = CloudApiClient.getInstance()
