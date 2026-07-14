-- FireGuard 云平台数据库结构
-- 库: dev_fireguard  (MySQL 8.x, utf8mb4)
--
-- 使用方式:
--   mysql -h 8.140.28.233 -u <user> -p dev_fireguard < schema.sql
--
-- 说明:
--   fire_alarm 为烟火告警主表, 只存"确认的告警事件"(confirmed_fire /
--   suspected_smoke / ai_unavailable), 不存逐帧检测.
--   幂等去重依赖 uk_event_type (event_id + alarm_type) 唯一索引.

CREATE TABLE IF NOT EXISTS fire_alarm (
  id                    BIGINT       NOT NULL AUTO_INCREMENT,
  event_id              VARCHAR(64)  NOT NULL              COMMENT '车端事件ID, 形如 fire_20260712_143052_123456_001',
  alarm_type            VARCHAR(32)  NOT NULL              COMMENT 'confirmed_fire / suspected_smoke / ai_unavailable',
  occurred_at           DATETIME(6)  NOT NULL              COMMENT '事件发生时刻(车端时间, 带微秒)',
  reason                VARCHAR(300) NULL                  COMMENT 'AI复核原因',
  confidence            DECIMAL(4,3) NULL                  COMMENT 'AI置信度 0.000~1.000',
  evidence_url          VARCHAR(512) NULL                  COMMENT '证据图片URL(Nginx静态目录)',
  detection_classes     VARCHAR(64)  NULL                  COMMENT '命中类别, 如 fire,smoke',
  max_confidence        DECIMAL(4,3) NULL                  COMMENT '本地检测最大置信度',
  local_detection_gone  TINYINT(1)   NOT NULL DEFAULT 0    COMMENT '告警时本地目标是否已消失',
  car_id                VARCHAR(32)  NOT NULL DEFAULT 'unknown' COMMENT '车辆标识(多车动态区分)',
  received_at           DATETIME(6)  NOT NULL              COMMENT '云端入库时刻(服务器时间)',
  raw_payload           JSON         NULL                  COMMENT '原始上报JSON存档',
  PRIMARY KEY (id),
  UNIQUE KEY uk_event_type (event_id, alarm_type),
  KEY idx_occurred (occurred_at),
  KEY idx_type (alarm_type),
  KEY idx_car (car_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='烟火告警事件表';
