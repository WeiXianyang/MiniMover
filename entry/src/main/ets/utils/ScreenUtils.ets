import window from '@ohos.window'
import common from '@ohos.app.ability.common'
import { BusinessError } from '@ohos.base'

export namespace ScreenUtils {

  /**
   * 保持屏幕常量
   * @param status
   */
  export async function keepScreenOn(ctx: common.BaseContext, status: boolean) {
    // let context = getContext(this) as common.BaseContext
    let windowClass = await window.getLastWindow(ctx) //获取窗口实例
    let isScreenOn = await windowClass.getWindowProperties().isKeepScreenOn //查看屏幕常亮状态
    if (!isScreenOn) {
      await windowClass.setWindowKeepScreenOn(status) //设置窗口常亮或取消
    }
    console.info("屏幕常亮状态： " + isScreenOn)
  }

  /**
   * 设置导航栏，状态栏不可见，在api9以后不能使用
   */
  export async function setSystemBarEnable_api9(ctx: common.BaseContext) {
    let windowClass = await window.getLastWindow(ctx)
    await windowClass.setWindowSystemBarEnable([])
  }


  /**
   * 设置导航栏，状态栏不可见，在api9以后不能使用
   */
  export async function setSystemBarEnable_api10(windowStage: window.WindowStage) {
    let windowClass: window.Window = windowStage.getMainWindowSync(); // 获取应用主窗口
    // 1. 设置窗口全屏
    let isLayoutFullScreen = true;
    windowClass.setWindowLayoutFullScreen(isLayoutFullScreen)
      .then(() => {
        console.info('Succeeded in setting the window layout to full-screen mode.');
      })// .catch((err: BusinessError) => {
      .catch((err: BusinessError) => {
        console.error('Failed to set the window layout to full-screen mode. Cause:' + JSON.stringify(err));
      });
  }


  /**
   * 获取系统状态栏（顶部安全区）高度，单位 vp。
   * 全屏布局下内容会延伸到状态栏下方，用此高度做顶部内边距可避免与电量/时间重叠。
   */
  export async function getStatusBarHeight(ctx: common.BaseContext): Promise<number> {
    let windowClass = await window.getLastWindow(ctx)
    let avoidArea = windowClass.getWindowAvoidArea(window.AvoidAreaType.TYPE_SYSTEM)
    return px2vp(avoidArea.topRect.height)
  }

  /**
   * 获取底部安全区（导航条/手势指示条）高度，单位 vp。
   */
  export async function getBottomSafeHeight(ctx: common.BaseContext): Promise<number> {
    let windowClass = await window.getLastWindow(ctx)
    let avoidArea = windowClass.getWindowAvoidArea(window.AvoidAreaType.TYPE_NAVIGATION_INDICATOR)
    return px2vp(avoidArea.bottomRect.height)
  }

  /**
   * 将应用设置为横屏
   */
  export function setLandscape(ctx: common.BaseContext) {
    //将应用设置为横屏
    let promise = window.getLastWindow(ctx);
    promise.then((data) => {
      //切换成横屏
      let orientation = window.Orientation.LANDSCAPE;
      data.setPreferredOrientation(orientation, (err) => {
      });
    })
  }


  /**
   * 将应用设置为竖屏
   */
  export function setPortrait(ctx: common.BaseContext) {
    //将应用设置为竖屏
    let promise = window.getLastWindow(ctx);
    promise.then((data) => {
      //切换成竖屏
      let orientation = window.Orientation.PORTRAIT;
      data.setPreferredOrientation(orientation, (err) => {
      });
    })
  }


}