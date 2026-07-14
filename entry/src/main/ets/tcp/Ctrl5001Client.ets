/**
 * 5001 低延迟控制通道客户端（单例）
 * 对接《小车端功能对接文档》2.8 节：纯文本 TCP，与 :5000 同 IP 同进程。
 * 协议：每行一条 "<cmd> [speed_pct] [duration_sec]\n"，fire-and-forget 无返回。
 * 用途：REST 模式下摇杆/急停走此通道（~2-5ms），旁路 HTTP 栈降低延迟。
 */
import socket from '@ohos.net.socket'

const TAG = 'Ctrl5001Client'

class Ctrl5001Client {
  private static instance: Ctrl5001Client | undefined = undefined
  private tcp: socket.TCPSocket = socket.constructTCPSocketInstance()
  private ip: string = ''
  private port: number = 5001
  /** 是否已建立连接（本地标记，配合 getState 兜底） */
  private connected: boolean = false

  static getInstance(): Ctrl5001Client {
    if (!Ctrl5001Client.instance) {
      Ctrl5001Client.instance = new Ctrl5001Client()
    }
    return Ctrl5001Client.instance
  }

  /** 设定目标地址（不立即连接） */
  init(ip: string, port: number): void {
    this.ip = ip
    this.port = port
  }

  isConnected(): boolean {
    return this.connected
  }

  /** 建立长连接，返回是否成功 */
  async connect(): Promise<boolean> {
    if (this.ip.length === 0) {
      return false
    }
    // 已连接则先关闭重连，避免重复绑定
    if (this.connected) {
      try {
        await this.tcp.close()
      } catch (e) {
        // 忽略关闭异常
      }
      this.connected = false
    }
    try {
      await this.tcp.bind({ address: '0.0.0.0', family: 1 })
      await this.tcp.connect({
        address: { address: this.ip, port: this.port },
        timeout: 2000
      })
      this.connected = true
      console.log(TAG, `connected ${this.ip}:${this.port}`)
      return true
    } catch (e) {
      console.error(TAG, `connect failed: ${JSON.stringify(e)}`)
      try {
        await this.tcp.close()
      } catch (e2) {
        // 忽略
      }
      this.connected = false
      return false
    }
  }

  /**
   * 发送控制命令。cmd 见文档：
   * forward/backward/left/right/rotate_left/rotate_right/left_shift/right_shift/stop
   * 返回是否成功送出（未连接返回 false，由上层回退 HTTP）
   */
  async send(cmd: string, speed: number, duration: number): Promise<boolean> {
    if (!this.connected) {
      return false
    }
    const line: string = `${cmd} ${speed} ${duration}\n`
    try {
      await this.tcp.send({ data: line })
      return true
    } catch (e) {
      console.error(TAG, `send failed: ${JSON.stringify(e)}`)
      this.connected = false
      return false
    }
  }

  /** 停止（stop 无需 speed/duration，但补齐以统一格式） */
  sendStop(): Promise<boolean> {
    return this.send('stop', 0, 0)
  }

  close(): void {
    if (this.connected) {
      this.tcp.close()
      this.connected = false
    }
  }
}

export const ctrl5001Client: Ctrl5001Client = Ctrl5001Client.getInstance()
