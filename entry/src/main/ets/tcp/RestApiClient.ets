/**
 * REST API 客户端（单例）
 * 通过 HTTP/JSON 与 Flask api_server.py 通信
 */
import http from '@ohos.net.http'

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

  /**
   * POST /api/move
   * 发送移动命令
   */
  sendMove(cmd: string, speed: number, duration: number): Promise<boolean> {
    return new Promise<boolean>((resolve: (value: boolean) => void) => {
      const req = http.createHttp()
      const body = JSON.stringify({ cmd: cmd, speed: speed, duration: duration })
      req.request(`${this.baseUrl}/api/move`, {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: body
      }).then(() => {
        resolve(true)
      }).catch((err: Error) => {
        console.error(`[RestApiClient] sendMove failed: ${JSON.stringify(err)}`)
        resolve(false)
      }).finally(() => {
        req.destroy()
      })
    })
  }

  /**
   * POST /api/move (不带 duration，用于持续移动)
   */
  sendMoveContinuous(cmd: string, speed: number): Promise<boolean> {
    return new Promise<boolean>((resolve: (value: boolean) => void) => {
      const req = http.createHttp()
      const body = JSON.stringify({ cmd: cmd, speed: speed })
      req.request(`${this.baseUrl}/api/move`, {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: body
      }).then(() => {
        resolve(true)
      }).catch((err: Error) => {
        console.error(`[RestApiClient] sendMoveContinuous failed: ${JSON.stringify(err)}`)
        resolve(false)
      }).finally(() => {
        req.destroy()
      })
    })
  }

  /**
   * GET /api/health
   * 健康检查
   */
  checkHealth(): Promise<boolean> {
    return new Promise<boolean>((resolve: (value: boolean) => void) => {
      const req = http.createHttp()
      req.request(`${this.baseUrl}/api/health`, {
        method: http.RequestMethod.GET
      }).then(() => {
        resolve(true)
      }).catch((err: Error) => {
        console.error(`[RestApiClient] checkHealth failed: ${JSON.stringify(err)}`)
        resolve(false)
      }).finally(() => {
        req.destroy()
      })
    })
  }

  /**
   * GET /api/status
   * 获取传感器状态数据
   */
  getStatus(): Promise<object | null> {
    return new Promise<object | null>((resolve: (value: object | null) => void) => {
      const req = http.createHttp()
      req.request(`${this.baseUrl}/api/status`, {
        method: http.RequestMethod.GET
      }).then((resp: http.HttpResponse) => {
        const data: object = JSON.parse(resp.result as string)
        resolve(data)
      }).catch((err: Error) => {
        console.error(`[RestApiClient] getStatus failed: ${JSON.stringify(err)}`)
        resolve(null)
      }).finally(() => {
        req.destroy()
      })
    })
  }
}

export const restApiClient: RestApiClient = RestApiClient.getInstance()
