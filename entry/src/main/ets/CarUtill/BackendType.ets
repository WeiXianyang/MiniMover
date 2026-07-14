/**
 * 后端连接类型枚举与全局状态
 * 用于在 TCP 二进制协议 与 REST API (Flask) 之间切换
 */
export enum BackendType {
  TCP = 0,
  REST = 1
}

export class BackendState {
  static type: BackendType = BackendType.TCP
  static connected: boolean = false
  static ip: string = '192.168.137.23'
  static tcpPort: number = 6000
  static restPort: number = 5000
  static videoPort: number = 6500
}
