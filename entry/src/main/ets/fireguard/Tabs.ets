/**
 * FireGuard 底部导航标签定义
 * 对应页面原型的 7 项 tabbar：连接 / 主页 / 地图 / 告警 / 配送 / 接管 / 报告
 */
export enum FgTab {
  Connect = 0,
  Home = 1,
  Map = 2,
  Alert = 3,
  Delivery = 4,
  Manual = 5,
  Report = 6
}

/** tab 顺序与短标题 */
export const FG_TAB_LABELS: string[] = ['连接', '主页', '地图', '告警', '配送', '接管', '报告'];
