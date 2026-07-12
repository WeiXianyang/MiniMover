/**
 * FireGuard 工业巡检 APP 设计系统
 * 颜色与尺寸取自页面原型 styles.css 的 :root 变量。
 */
export namespace FG {
  // ---- 颜色 ----
  export const bg: string = '#071018';          // 页面底色
  export const phone: string = '#101927';       // 手机框
  export const panel: string = '#172435';       // 卡片层
  export const panel2: string = '#1e2c3f';      // 次级面板
  export const line: string = '#2a3d56';        // 边框
  export const text: string = '#eef4ff';        // 主文字
  export const muted: string = '#93a4ba';       // 次要文字
  export const orange: string = '#ff9748';      // 主品牌/推荐
  export const cyan: string = '#30d3ff';        // 路径/数据
  export const green: string = '#63e6a7';       // 正常状态
  export const red: string = '#ff6570';         // 告警/危险

  // 卡片背景（带透明度）
  export const cardBg: string = 'rgba(24, 37, 55, 0.9)';
  export const inputBg: string = '#223247';
  export const inputBorder: string = '#33475f';
  export const barTrack: string = '#26364a';
  export const btnDefault: string = '#28384b';
  export const tabbarBg: string = 'rgba(10, 17, 27, 0.94)';

  // pill 背景
  export const pillGreenBg: string = 'rgba(99, 230, 167, 0.14)';
  export const pillOrangeBg: string = 'rgba(255, 151, 72, 0.17)';
  export const pillRedBg: string = 'rgba(255, 101, 112, 0.2)';
  export const pillGreenText: string = '#dcfff0';
  export const pillOrangeText: string = '#fff0df';
  export const pillRedText: string = '#fff2f3';

  // ---- 字号（fp）----
  export const titleSize: number = 24;
  export const metricSize: number = 23;
  export const recommendSize: number = 18;
  export const bodySize: number = 13;
  export const labelSize: number = 12;
  export const smallSize: number = 11;

  // ---- 圆角（vp）----
  export const cardRadius: number = 12;
  export const btnRadius: number = 10;
  export const pillRadius: number = 999;
}
