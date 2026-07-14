# 云端 API 接口文档（前端对接）

> 基础地址：`http://8.140.28.233:8000`
> 响应格式：统一 `{"code": 0, "msg": "ok", ...}`
> 鉴权方式：请求头 `Authorization: Bearer <API_TOKEN>`（未开启鉴权时可不带）

---

## 通用约定

### 响应格式

所有接口返回统一 JSON 结构：

```json
{
  "code": 0,
  "msg": "ok",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 0 = 成功，其他 = 错误 |
| `msg` | string | 状态描述 |
| `data` | object/array | 实际数据（错误时不返回） |
| `error` | string | 错误详情（仅错误时返回） |

### 错误码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 400 | 请求参数错误（`msg` 中有具体说明） |
| 401 | 未授权（token 缺失或错误） |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 鉴权

每个需要鉴权的接口需在请求头中携带：

```
Authorization: Bearer <API_TOKEN>
```

若云端 `API_TOKEN` 为空，鉴权自动跳过，可不带此 header。

---

## 接口列表

### 1. 健康检查 `GET /healthz`

无需鉴权。

**响应示例：**
```json
{
  "code": 0,
  "msg": "ok",
  "db": "up"
}
```

若返回 `"db": "down"`，表示数据库不可用，其他接口都会 500。

---

### 2. 告警列表 `GET /api/v1/fire-alarms`

**鉴权**：是

**查询参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `page` | int | 否 | 1 | 页码，从 1 开始 |
| `size` | int | 否 | 20 | 每页条数，最大 200 |
| `type` | string | 否 | - | 告警类型：`confirmed_fire` / `suspected_smoke` / `ai_unavailable` |
| `car_id` | string | 否 | - | 车辆标识 |
| `from` | string | 否 | - | 开始时间，ISO8601 格式（含时区） |
| `to` | string | 否 | - | 结束时间，ISO8601 格式（含时区） |

**请求示例：**
```
GET /api/v1/fire-alarms?page=1&size=20&type=confirmed_fire&car_id=car-01&from=2026-07-01T00:00:00%2B08:00&to=2026-07-31T23:59:59%2B08:00
```

> URL 中 `+` 需编码为 `%2B`，或用不带 `:` 和 `+` 的格式如 `2026-07-01T00:00:00`

**响应 `data` 结构：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 符合条件的总记录数 |
| `page` | int | 当前页码 |
| `size` | int | 每页条数 |
| `items` | array | 告警记录列表 |

**`items[].` 字段：**

| 字段 | 类型 | 可空 | 说明 |
|------|------|------|------|
| `id` | int | 否 | 自增主键 |
| `event_id` | string | 否 | 车端事件 ID |
| `alarm_type` | string | 否 | `confirmed_fire` / `suspected_smoke` / `ai_unavailable` |
| `occurred_at` | string | 否 | 事件发生时间，ISO8601 格式 |
| `reason` | string | 是 | AI 复核原因中文描述 |
| `confidence` | number | 是 | AI 置信度，0.0~1.0（`ai_unavailable` 时为 null） |
| `evidence_url` | string | 是 | 证据图片 URL |
| `detection_classes` | string | 是 | 命中类别，如 `fire,smoke` |
| `max_confidence` | number | 是 | 本地 YOLO 检测最大置信度 |
| `local_detection_gone` | boolean | 否 | 告警时本地目标是否已消失 |
| `car_id` | string | 否 | 车辆标识 |
| `received_at` | string | 否 | 云端接收时间，ISO8601 |

**响应示例：**
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "total": 2,
    "page": 1,
    "size": 20,
    "items": [
      {
        "id": 2,
        "event_id": "fire_20260713_143052_123456_001",
        "alarm_type": "confirmed_fire",
        "occurred_at": "2026-07-13T14:30:52.123456+08:00",
        "reason": "画面中部可见明显跳动火焰",
        "confidence": 0.91,
        "evidence_url": "http://8.140.28.233/evidence/fire_20260713_143052_123456_001_001_initial_143052.jpg",
        "detection_classes": "fire",
        "max_confidence": 0.88,
        "local_detection_gone": false,
        "car_id": "car-01",
        "received_at": "2026-07-13T14:30:55.654321+08:00"
      },
      {
        "id": 1,
        "event_id": "fire_20260713_120000_654321_001",
        "alarm_type": "suspected_smoke",
        "occurred_at": "2026-07-13T12:00:00.000000+08:00",
        "reason": "画面左上角有疑似烟雾扩散",
        "confidence": 0.72,
        "evidence_url": "http://8.140.28.233/evidence/fire_20260713_120000_654321_001_001_initial_120000.jpg",
        "detection_classes": "smoke",
        "max_confidence": 0.75,
        "local_detection_gone": false,
        "car_id": "car-01",
        "received_at": "2026-07-13T12:00:03.123456+08:00"
      }
    ]
  }
}
```

---

### 3. 告警详情 `GET /api/v1/fire-alarms/{id}`

**鉴权**：是

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | int | 告警记录 ID（来自列表的 `id` 字段） |

**请求示例：**
```
GET /api/v1/fire-alarms/1
```

**响应示例：**
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "id": 1,
    "event_id": "fire_20260713_143052_123456_001",
    "alarm_type": "confirmed_fire",
    "occurred_at": "2026-07-13T14:30:52.123456+08:00",
    "reason": "画面中部可见明显跳动火焰",
    "confidence": 0.91,
    "evidence_url": "http://8.140.28.233/evidence/fire_20260713_143052_123456_001_001_initial_143052.jpg",
    "detection_classes": "fire",
    "max_confidence": 0.88,
    "local_detection_gone": false,
    "car_id": "car-01",
    "received_at": "2026-07-13T14:30:55.654321+08:00",
    "raw_payload": {
      "event_id": "fire_20260713_143052_123456_001",
      "alarm_type": "confirmed_fire",
      "occurred_at": "2026-07-13T14:30:52.123456+08:00",
      "reason": "画面中部可见明显跳动火焰",
      "confidence": 0.91,
      "evidence_url": "http://8.140.28.233/evidence/fire_20260713_143052_123456_001_001_initial_143052.jpg",
      "detection_classes": ["fire"],
      "max_confidence": 0.88,
      "local_detection_gone": false,
      "car_id": "car-01"
    }
  }
}
```

与列表接口的区别：**额外包含 `raw_payload` 字段**，为车端上报的原始 JSON 完整存档。

---

## 前端调用封装

```javascript
// config.js
const API_BASE = 'http://8.140.28.233:8000';
const API_TOKEN = '';  // 鉴权关闭时留空，开启时填入

function request(path, options = {}) {
  const headers = { ...options.headers };
  if (API_TOKEN) headers['Authorization'] = `Bearer ${API_TOKEN}`;
  return fetch(`${API_BASE}${path}`, { ...options, headers })
    .then(async res => {
      const json = await res.json();
      if (json.code !== 0) throw { status: res.status, ...json };
      return json.data;
    });
}

// 告警列表
function getAlarms(params = {}) {
  const qs = new URLSearchParams({ page: 1, size: 20, ...params }).toString();
  return request(`/api/v1/fire-alarms?${qs}`);
}

// 告警详情
function getAlarmDetail(id) {
  return request(`/api/v1/fire-alarms/${id}`);
}

// 健康检查
function healthCheck() {
  return fetch(`${API_BASE}/healthz`).then(r => r.json());
}
```

---

## 常见错误示例

### 未授权（401）

```json
{"code": 401, "msg": "unauthorized"}
```

→ 检查 `API_TOKEN` 是否正确，或云端是否开启了鉴权。

### 参数错误（400）

```json
{"code": 400, "msg": "alarm_type must be one of ['ai_unavailable', 'confirmed_fire', 'suspected_smoke']"}
```

→ 传入的 `type` 值不合法。

### 资源不存在（404）

```json
{"code": 404, "msg": "not found"}
```

→ 传入的 `id` 对应的告警记录不存在。

### 数据库异常（500）

```json
{"code": 500, "msg": "db error", "error": "..."}
```

→ 后端数据库连接失败，联系运维排查。
