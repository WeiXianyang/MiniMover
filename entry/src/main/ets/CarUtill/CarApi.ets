import { TCPClientManager } from '../tcp/TCPClientManager'
import { TCPClientSendUtils } from '../tcp/TCPClientSendUtils'
import { CarEncode } from './CarEncode';
import { CarDirection } from './CarEnum';
import { BackendState, BackendType } from './BackendType';
import { restApiClient } from '../tcp/RestApiClient';

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

  /** REST: 发送移动命令（带持续时长） */
  sendRestMove(cmd: string, speed: number, duration: number): Promise<boolean> {
    return restApiClient.sendMove(cmd, speed, duration)
  }

  /** REST: 发送持续移动命令（不带持续时长，用于轮询） */
  sendRestMoveContinuous(cmd: string, speed: number): Promise<boolean> {
    return restApiClient.sendMoveContinuous(cmd, speed)
  }

  /** REST: 发送停止命令 */
  sendRestStop(): Promise<boolean> {
    return restApiClient.sendMove('stop', 0, 0)
  }
}

let carApi = (new CarApi())

export { carApi, }
