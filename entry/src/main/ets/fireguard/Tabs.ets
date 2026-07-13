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

/** tab icon 资源，顺序与 FgTab 枚举一致 */
export const FG_TAB_ICONS: Resource[] = [
  $r('app.media.plug'),
  $r('app.media.home'),
  $r('app.media.triangle-alert'),
  $r('app.media.route'),
  $r('app.media.car')
];
