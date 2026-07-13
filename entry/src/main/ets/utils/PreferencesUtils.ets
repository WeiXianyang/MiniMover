import preferences from '@ohos.data.preferences';

/**首选项对象*/
export class PreferencesUtils {
  /**私有静态实例，懒汉式单例*/
  private static instance: PreferencesUtils | undefined = undefined;

  /**私有构造方法，防止外部直接实例化*/
  private constructor() {
  }

  /**提供一个公共的静态方法返回实例对象*/
  public static getInstance(): PreferencesUtils {
    if (!PreferencesUtils.instance)
      PreferencesUtils.instance = new PreferencesUtils();
    return PreferencesUtils.instance;
  }

  /**网络工具对象*/
  netUtils!: NetInfoPreferencesUtils

  async init(context: Context) {
    this.netUtils = new NetInfoPreferencesUtils(context)
  }
}

/**
 * 网络配置首选项工具
 */
export class NetInfoPreferencesUtils {
  public static readonly NAME = "net_preferences_utils"
  public static readonly KEY_IP = "KEY_IP";
  public static readonly KEY_TCP_PORT = "KEY_TCP_PORT";
  public static readonly KEY_VIDEO_PORT = "KEY_TCP_VIDEO";
  public static readonly KEY_BACKEND_TYPE = "KEY_BACKEND_TYPE";
  public static readonly KEY_REST_PORT = "KEY_REST_PORT";
  private pref!: preferences.Preferences

  constructor(context: Context) {
    this.init(context)
  }

  private async init(context: Context) {
    let name = NetInfoPreferencesUtils.NAME;
    try {
      this.pref = await preferences.getPreferences(context, name)
      console.log(`preferences[${name}]初始化成功`)
    } catch (err) {
      console.error(`preferences[${name}]初始化失败`)
      console.error('err: ', JSON.stringify(err))
    }
  }

  // ------------------------------对外接口------------------------------

  async getIP(): Promise<string> {
    return (await this.pref.get(NetInfoPreferencesUtils.KEY_IP, '192.168.1.11')).toString()
  }

  setIp(v: string) {
    this.pref.put(NetInfoPreferencesUtils.KEY_IP, v);
    this.pref.flush()
  }

  async getTcpPort(): Promise<string> {
    return (await this.pref.get(NetInfoPreferencesUtils.KEY_TCP_PORT, '6000')).toString()
  }

  setTcpPort(v: string) {
    this.pref.put(NetInfoPreferencesUtils.KEY_TCP_PORT, v);
    this.pref.flush()
  }

  setVideoPort(v: string) {
    this.pref.put(NetInfoPreferencesUtils.KEY_VIDEO_PORT, v);
    this.pref.flush()
  }

  async getVideoPort(): Promise<string> {
    return (await this.pref.get(NetInfoPreferencesUtils.KEY_VIDEO_PORT, '6500')).toString()
  }

  // ------------------------------后端类型 + REST 端口------------------------------

  async getBackendType(): Promise<number> {
    return (await this.pref.get(NetInfoPreferencesUtils.KEY_BACKEND_TYPE, 0)) as number
  }

  setBackendType(v: number) {
    this.pref.put(NetInfoPreferencesUtils.KEY_BACKEND_TYPE, v);
    this.pref.flush()
  }

  async getRestPort(): Promise<string> {
    return (await this.pref.get(NetInfoPreferencesUtils.KEY_REST_PORT, '5000')).toString()
  }

  setRestPort(v: string) {
    this.pref.put(NetInfoPreferencesUtils.KEY_REST_PORT, v);
    this.pref.flush()
  }
}
