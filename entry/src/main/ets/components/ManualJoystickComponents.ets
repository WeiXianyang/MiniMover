/**
 * 手动接管摇杆组件（独立实现，不依赖 rocker 库）
 * 严格参照 manual-landscape.html 原型 CSS 样式：
 * - 移动摇杆：120×120 圆，十字准星 + 橙色中心旋钮，支持全向拖拽控制
 * - 视角摇杆：140×62 药丸形，橙色中心旋钮，支持水平拖拽
 */
import { CarDirection } from '../CarUtill/CarEnum'
import { BackendState, BackendType } from '../CarUtill/BackendType'
import { carApi } from '../CarUtill/CarApi'
import { FG } from '../fireguard/Theme'

/* ---- 内部工具 ---- */

/** 根据相对位移计算移动方向（取主导轴，映射到协议支持的四向 + 刹车） */
function directionFromOffset(x: number, y: number): CarDirection {
  const len = Math.sqrt(x * x + y * y)
  if (len < 8) return CarDirection.Brake
  // 屏幕坐标：y 向下为正。向上拖动 = 前进，向下 = 后退
  if (Math.abs(x) > Math.abs(y)) {
    return x > 0 ? CarDirection.Right : CarDirection.Left
  }
  return y > 0 ? CarDirection.After : CarDirection.Front
}

/** 20~100 速度 */
function speedFromOffset(dx: number, dy: number, maxR: number): number {
  const len = Math.sqrt(dx * dx + dy * dy)
  return Math.round(Math.max(20, Math.min(100, (len / maxR) * 100)))
}

/** REST 轮询方向字符串映射 */
function restDirCmd(d: CarDirection): string {
  // 对齐《小车端功能对接文档》/api/move：forward/backward/left/right/left_shift/right_shift/stop
  switch (d) {
    case CarDirection.Front: return 'forward'
    case CarDirection.After: return 'backward'
    case CarDirection.Left: return 'left_shift'
    case CarDirection.Right: return 'right_shift'
    case CarDirection.LeftRotate: return 'left'
    case CarDirection.RightRotate: return 'right'
    default: return 'stop'
  }
}

/* ======================= 运动摇杆 ======================= */

@Component
export struct ManualMoveJoystick {
  /** 旋钮相对中心偏移（vp）。0,0 = 居中 */
  @State knobX: number = 0
  @State knobY: number = 0
  private containerR: number = 60 // 摇杆容器半径
  private knobR: number = 26 // 旋钮半径
  private maxR: number = 34 // 最大偏移 (60 - 26)
  private lastDir: CarDirection | null = null
  private restTimer: number = -1

  aboutToDisappear(): void {
    if (this.restTimer !== -1) {
      clearInterval(this.restTimer)
      this.restTimer = -1
    }
  }

  build() {
    Stack() {
      // 背景圆 120×120
      Circle()
        .width(120)
        .height(120)
        .fill('rgba(14, 22, 31, 0.62)')
        .stroke('rgba(147, 164, 186, 0.24)').strokeWidth(1)

      // 准星十字线
      Line()
        .width(1)
        .height('100%')
        .stroke('rgba(147, 164, 186, 0.16)').strokeWidth(1)
      Line()
        .width('100%')
        .height(1)
        .stroke('rgba(147, 164, 186, 0.16)').strokeWidth(1)

      // 橙色旋钮 52×52，跟随拖拽偏移
      Circle()
        .width(52)
        .height(52)
        .fill(FG.orange)
        .translate({ x: this.knobX, y: this.knobY })
    }
    .width(120)
    .height(120)
    .borderRadius(FG.pillRadius)
    .border({ width: 1, color: 'rgba(147, 164, 186, 0.24)' })
    .gesture(
      PanGesture({ direction: PanDirection.All })
        .onActionStart(() => {
          // 仅记录起点
        })
        .onActionUpdate((event: GestureEvent) => {
          // 限制偏移不超过最大半径
          let dx = Math.max(-this.maxR, Math.min(this.maxR, event.offsetX))
          let dy = Math.max(-this.maxR, Math.min(this.maxR, event.offsetY))
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist > this.maxR) {
            const scale = this.maxR / dist
            dx *= scale
            dy *= scale
          }
          this.knobX = dx
          this.knobY = dy

          const dir = directionFromOffset(dx, dy)
          const speed = speedFromOffset(dx, dy, this.maxR)

          if (BackendState.type === BackendType.REST) {
            this.sendRest(dir, speed)
          } else {
            if (dir !== this.lastDir) {
              if (dir === CarDirection.Brake) {
                carApi.carBtnCtrl(CarDirection.Brake)
              } else {
                carApi.carBtnCtrl(dir)
              }
              this.lastDir = dir
            }
          }
        })
        .onActionEnd(() => {
          // 松手回中
          this.knobX = 0
          this.knobY = 0
          if (BackendState.type === BackendType.REST) {
            this.stopRest()
            carApi.sendRestStop()
          } else {
            carApi.carBtnCtrl(CarDirection.Brake)
            this.lastDir = null
          }
        })
    )
  }

  private sendRest(dir: CarDirection, speed: number): void {
    if (dir === CarDirection.Brake) {
      this.stopRest()
      carApi.sendRestStop()
      return
    }
    const cmd = restDirCmd(dir)
    if (this.restTimer === -1) {
      carApi.sendRestMoveContinuous(cmd, speed)
      this.restTimer = setInterval(() => {
        carApi.sendRestMoveContinuous(cmd, speed)
      }, 300)
    }
  }

  private stopRest(): void {
    if (this.restTimer !== -1) {
      clearInterval(this.restTimer)
      this.restTimer = -1
    }
  }
}

/* ======================= 视角/云台摇杆 ======================= */

@Component
export struct ManualViewJoystick {
  @State knobX: number = 0
  private maxDx: number = 34 // 最大水平偏移
  private viewTimer: number = -1

  aboutToDisappear(): void {
    if (this.viewTimer !== -1) {
      clearInterval(this.viewTimer)
      this.viewTimer = -1
    }
  }

  build() {
    Stack() {
      // 药丸形背景 140×62
      Row()
        .width(140)
        .height(62)
        .borderRadius(FG.pillRadius)
        .border({ width: 1, color: 'rgba(147, 164, 186, 0.24)' })
        .backgroundColor('rgba(14, 22, 31, 0.62)')

      // 橙色旋钮 52×52，跟随水平拖拽偏移
      Circle()
        .width(52)
        .height(52)
        .fill(FG.orange)
        .translate({ x: this.knobX, y: 0 })
    }
    .width(140)
    .height(62)
    .gesture(
      PanGesture({ direction: PanDirection.Horizontal })
        .onActionUpdate((event: GestureEvent) => {
          this.knobX = Math.max(-this.maxDx, Math.min(this.maxDx, event.offsetX))
          // 视角摇杆当前仅输出调试日志
        })
        .onActionEnd(() => {
          this.knobX = 0
        })
    )
  }
}
