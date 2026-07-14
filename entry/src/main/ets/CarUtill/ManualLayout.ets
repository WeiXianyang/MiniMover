/**
 * 手动接管页布局全局存储
 * 布局设置页保存位置到此，横屏接管页读取应用。
 * 位置以「占舞台宽/高的比例(0~1)」存储，兼容两页不同的实际渲染尺寸。
 */
export class ManualLayout {
  /** 是否已自定义（未定义则接管页用默认锚定布局） */
  static customized: boolean = false
  /** 移动摇杆左上角比例坐标 */
  static moveXR: number = 0
  static moveYR: number = 0
  /** 雷达小窗左上角比例坐标 */
  static radarXR: number = 0
  static radarYR: number = 0
  /** 视角摇杆左上角比例坐标 */
  static viewXR: number = 0
  static viewYR: number = 0
}
