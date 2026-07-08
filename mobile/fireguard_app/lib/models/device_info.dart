/// 小车设备连接信息
class DeviceInfo {
  final String ip;
  final int tcpPort;
  final int videoPort;
  final bool isOnline;
  final String lastTask;
  final String lastConnectTime;
  final String deviceStatus;

  const DeviceInfo({
    this.ip = '192.168.1.11',
    this.tcpPort = 6000,
    this.videoPort = 6500,
    this.isOnline = true,
    this.lastTask = '07-07 上午巡检',
    this.lastConnectTime = '09:26',
    this.deviceStatus = 'Jetson / ROS2 / 视频服务正常',
  });

  DeviceInfo copyWith({
    String? ip,
    int? tcpPort,
    int? videoPort,
    bool? isOnline,
    String? lastTask,
    String? lastConnectTime,
    String? deviceStatus,
  }) {
    return DeviceInfo(
      ip: ip ?? this.ip,
      tcpPort: tcpPort ?? this.tcpPort,
      videoPort: videoPort ?? this.videoPort,
      isOnline: isOnline ?? this.isOnline,
      lastTask: lastTask ?? this.lastTask,
      lastConnectTime: lastConnectTime ?? this.lastConnectTime,
      deviceStatus: deviceStatus ?? this.deviceStatus,
    );
  }
}

/// 巡检状态
class InspectionState {
  final String area;
  final String task;
  final int battery;
  final int pendingPoints;
  final String smokeStatus;
  final double temperature;
  final String recommendation;
  final String status;

  const InspectionState({
    this.area = '园区 A 栋一层',
    this.task = '配电房与仓储通道巡检',
    this.battery = 86,
    this.pendingPoints = 4,
    this.smokeStatus = '正常',
    this.temperature = 29.0,
    this.recommendation = '开始自动巡检，预计 6 分钟完成',
    this.status = '自动巡检待命',
  });
}

/// 告警信息
class AlarmInfo {
  final String location;
  final double confidence;
  final int smokeValue;
  final double temperature;
  final String suggestion;
  final String level;

  const AlarmInfo({
    this.location = '配电柜A 北侧',
    this.confidence = 0.93,
    this.smokeValue = 86,
    this.temperature = 67.0,
    this.suggestion = '建议先停车并拉起远程接管，同时发起应急物资配送。',
    this.level = '高等级告警',
  });
}

/// 配送信息
class DeliveryInfo {
  final String supplies;
  final String startPoint;
  final String endPoint;
  final String path;
  final int progress;
  final String status;
  final String cargoStatus;
  final String confirmStatus;

  const DeliveryInfo({
    this.supplies = '灭火器模型 / 急救包',
    this.startPoint = '应急物资点D',
    this.endPoint = '配电柜A',
    this.path = 'D 点装载 → 主通道 → 配电柜A',
    this.progress = 68,
    this.status = '配送中',
    this.cargoStatus = '已锁定',
    this.confirmStatus = '待现场人员签收',
  });
}

/// 巡检报告
class InspectionReport {
  final String duration;
  final int completedPoints;
  final int totalPoints;
  final int highAlerts;
  final int dynamicObstacles;
  final List<ReportEvent> events;

  const InspectionReport({
    this.duration = '6m 28s',
    this.completedPoints = 4,
    this.totalPoints = 4,
    this.highAlerts = 1,
    this.dynamicObstacles = 2,
    this.events = const [
      ReportEvent('事件 01', '配电柜A 发现疑似烟雾'),
      ReportEvent('事件 02', '仓储通道纸箱避障成功'),
    ],
  });
}

class ReportEvent {
  final String label;
  final String description;

  const ReportEvent(this.label, this.description);
}
