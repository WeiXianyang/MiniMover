/**
 * FireGuard 底部导航标签定义
 * 对应页面原型的 5 项 tabbar：连接 / 主页 / 告警 / 配送 / 编队
 */
export enum FgTab {
  Connect = 0,
  Home = 1,
  Alert = 2,
  Delivery = 3,
  Fleet = 4
}

/** tab 顺序与短标题 */
export const FG_TAB_LABELS: string[] = ['连接', '主页', '告警', '配送', '编队'];
