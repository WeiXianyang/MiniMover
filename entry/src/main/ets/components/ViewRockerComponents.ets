/**
 * 视角 / 云台摇杆组件（占位）
 * 用于横屏手动接管页面右下角视角控制，
 * 当前仅输出调试日志，不发送网络指令（摄像头/云台控制暂不在 REST API 中）
 */
import { RockerComponent, RockerOptions } from "rocker"

@Component
struct ViewRockerComponents {
  tiltStyle = new ImageBitmap("img/remote.svg")
  backgroundStyle = new ImageBitmap("img/remote_background.svg")

  build() {
    RockerComponent({
      rockerOptions: {
        tiltWidth: 0.4,
        getTiltStyle: (): ImageBitmap => this.tiltStyle,
        getBackgroundStyle: (): ImageBitmap => this.backgroundStyle,
        tiltEvent: (tiltX: number, tiltY: number, event?: TouchEvent) => {
          console.info(`[ViewRocker] tilt X=${tiltX.toFixed(1)} Y=${tiltY.toFixed(1)}`)
        }
      }
    })
  }
}

export { ViewRockerComponents }
