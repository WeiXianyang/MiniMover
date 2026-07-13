import { carApi } from '../CarUtill/CarApi'
import { CarEncode } from '../CarUtill/CarEncode';
import { BackendState, BackendType } from '../CarUtill/BackendType';

import { RockerComponent, RockerOptions } from "rocker"

let TAG = 'anran0';

/** XY 摇杆值 → REST 方向命令映射 */
function tiltToDirection(tiltX: number, tiltY: number): string {
  if (Math.abs(tiltX) > Math.abs(tiltY)) {
    return tiltX > 0 ? 'Right' : 'Left';
  } else {
    return tiltY > 0 ? 'Back' : 'Forward';
  }
}

/** 死区阈值 */
const DEAD_ZONE: number = 15;

/**
 * 摇杆控制UI组件
 * 支持 TCP 和 REST 两种后端模式
 */
@Component
struct CarRockerComponents {
  tiltStyle = new ImageBitmap("img/remote.svg");
  backgroundStyle = new ImageBitmap("img/remote_background.svg");

  private restInterval: number = -1;

  aboutToDisappear(): void {
    if (this.restInterval !== -1) {
      clearInterval(this.restInterval);
      this.restInterval = -1;
    }
  }

  build() {
    RockerComponent({
      rockerOptions: {
        tiltWidth: 0.6,
        getTiltStyle: (): ImageBitmap => this.tiltStyle,
        getBackgroundStyle: (): ImageBitmap => this.backgroundStyle,
        tiltEvent: (tiltX: number, tiltY: number, event?: TouchEvent) => {
          if (BackendState.type === BackendType.REST) {
            this.handleRestTilt(tiltX, tiltY);
          } else {
            carApi.send(CarEncode.CtrlCarEncode(tiltX, tiltY));
          }
        }
      }
    })
  }

  private handleRestTilt(tiltX: number, tiltY: number): void {
    const magnitude: number = Math.sqrt(tiltX * tiltX + tiltY * tiltY);

    if (magnitude < DEAD_ZONE) {
      // 摇杆归零 → 清除轮询并停止
      if (this.restInterval !== -1) {
        clearInterval(this.restInterval);
        this.restInterval = -1;
      }
      carApi.sendRestStop();
      return;
    }

    const dir: string = tiltToDirection(tiltX, tiltY);
    const speed: number = Math.min(100, Math.max(20, Math.round(magnitude)));

    // 启动轮询（如果尚未启动）
    if (this.restInterval === -1) {
      this.restInterval = setInterval(() => {
        const curDir: string = tiltToDirection(tiltX, tiltY);
        const curMag: number = Math.sqrt(tiltX * tiltX + tiltY * tiltY);
        const curSpeed: number = Math.min(100, Math.max(20, Math.round(curMag)));
        carApi.sendRestMoveContinuous(curDir, curSpeed);
      }, 300);
    }

    // 立即发送一次
    carApi.sendRestMoveContinuous(dir, speed);
  }
}

export { CarRockerComponents }
