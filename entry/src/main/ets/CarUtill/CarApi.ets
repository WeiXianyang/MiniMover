import { TCPClientManager } from '../tcp/TCPClientManager'
import { TCPClientSendUtils } from '../tcp/TCPClientSendUtils'
import { CarEncode } from './CarEncode';
import { CarDirection } from './CarEnum';
import { BackendState, BackendType } from './BackendType';
import { restApiClient } from '../tcp/RestApiClient';

function directionToRestCmd(d: CarDirection): string {
  switch (d) {
    case CarDirection.Front: return 'forward';
    case CarDirection.After: return 'backward';
    case CarDirection.Left: return 'left';
    case CarDirection.Right: return 'right';
    case CarDirection.LeftRotate: return 'rotate_left';
    case CarDirection.RightRotate: return 'rotate_right';
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
