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
  static videoPort: number = 8080  // ROS2 web_video_server（8080），弃用旧版 6500
  /** 5001 低延迟控制通道端口（固定，与 restPort 同 IP 同进程） */
  static ctrlPort: number = 5001
  /** 5001 控制通道是否已连通（决定摇杆走 5001 还是回退 HTTP） */
  static ctrlConnected: boolean = false
}
