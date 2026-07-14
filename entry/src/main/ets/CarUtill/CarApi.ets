import { TCPClientManager } from '../tcp/TCPClientManager'
import { TCPClientSendUtils } from '../tcp/TCPClientSendUtils'
import { CarEncode } from './CarEncode';
import { CarDirection } from './CarEnum';
import { BackendState, BackendType } from './BackendType';
import { restApiClient } from '../tcp/RestApiClient';
import { ctrl5001Client } from '../tcp/Ctrl5001Client';

function directionToRestCmd(d: CarDirection): string {
  // 对齐《小车端功能对接文档》/api/move：仅 forward/backward/left/right/left_shift/right_shift/stop
  // CarEnum 中 Left/Right 为麦轮平移，LeftRotate/RightRotate 为转向
  switch (d) {
    case CarDirection.Front: return 'forward';
    case CarDirection.After: return 'backward';
    case CarDirection.Left: return 'left_shift';
    case CarDirection.Right: return 'right_shift';
    case CarDirection.LeftRotate: return 'left';
    case CarDirection.RightRotate: return 'right';
    default: return 'stop';
  }
}

class CarApi {
  carBtnCtrl(d: CarDirection): void {
    if (BackendState.type === BackendType.REST) {
      const cmd: string = directionToRestCmd(d);
      this.sendRestMove(cmd, 60, 300);
    } else {
      this.send(CarEncode.ButtonCarEncode(d))
    }
  }

  send(message: string): void {
    TCPClientManager.getInstance().sendMessage(message)
  }

  /**
   * REST: 发送移动命令（带持续时长）
   * 优先走 5001 低延迟通道，未连通则回退 HTTP /api/move。
   */
  async sendRestMove(cmd: string, speed: number, duration: number): Promise<boolean> {
    if (BackendState.ctrlConnected) {
      const ok: boolean = await ctrl5001Client.send(cmd, speed, duration / 1000)
      if (ok) {
        return true
      }
      // 5001 send 失败（可能断线），标记并回退
      BackendState.ctrlConnected = false
    }
    return restApiClient.sendMove(cmd, speed, duration)
  }

  /**
   * REST: 发送持续移动命令（不带持续时长，用于摇杆轮询）
   * 5001 通道给一个短 duration 兜底自动停，回退 HTTP 时不带 duration。
   */
  async sendRestMoveContinuous(cmd: string, speed: number): Promise<boolean> {
    if (BackendState.ctrlConnected) {
      const ok: boolean = await ctrl5001Client.send(cmd, speed, 0.5)
      if (ok) {
        return true
      }
      BackendState.ctrlConnected = false
    }
    return restApiClient.sendMoveContinuous(cmd, speed)
  }

  /** REST: 发送停止命令，优先 5001，回退 HTTP */
  async sendRestStop(): Promise<boolean> {
    if (BackendState.ctrlConnected) {
      const ok: boolean = await ctrl5001Client.sendStop()
      if (ok) {
        return true
      }
      BackendState.ctrlConnected = false
    }
    return restApiClient.sendMove('stop', 0, 0)
  }
}

let carApi = (new CarApi())

export { carApi, }
