# FireGuard 云端接收 API 部署指南

> 目标服务器：8.140.28.233
> MySQL：同一台机器上，`dev_fireguard` 库

---

## 一、环境要求

| 组件 | 要求 |
|------|------|
| OS | Linux (CentOS / Ubuntu) |
| Python | 3.8+ |
| MySQL | 已部署于本机 3306 |
| Nginx | 静态图片反代 (可选，若无则图片 URL 不可公网访问) |

---

## 二、部署步骤

### 1. 传代码到服务器

```bash
# 方式一：git clone (推荐)
cd /opt
git clone https://github.com/WeiXianyang/MiniMover.git
cd MiniMover/cloud_platform

# 方式二：scp 上传
# 在本地执行: scp -r cloud_platform/ root@8.140.28.233:/opt/cloud_platform/
# 然后 ssh 到服务器: cd /opt/cloud_platform
```

### 2. 建表

```bash
mysql -h 127.0.0.1 -u root -p dev_fireguard < schema.sql
# 输入密码: wishwithyou
```

验证：
```bash
mysql -h 127.0.0.1 -u root -p dev_fireguard -e "DESC fire_alarm;"
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，修改以下字段：

```ini
# 数据库（只改密码，其他保持默认）
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=wishwithyou
DB_NAME=dev_fireguard

# 生成一个随机 token（在服务器上执行 python3 -c "import secrets; print(secrets.token_urlsafe(24))"）
API_TOKEN=<你生成的随机 token>

# API 端口
API_PORT=8000

# 证据图片存储和对外 URL
EVIDENCE_DIR=/data/fireguard/evidence
EVIDENCE_BASE_URL=http://8.140.28.233/evidence
MAX_UPLOAD_MB=10
```

### 4. 创建证据图片目录

```bash
mkdir -p /data/fireguard/evidence
chmod 755 /data/fireguard/evidence
```

### 5. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 6. 启动服务

**调试模式**（前台，Ctrl+C 停止）：
```bash
python -m cloud_platform.server
```

**生产模式**（gunicorn 多进程，后台运行）：
```bash
# 安装 gunicorn（requirements.txt 里已有，如无则 pip install gunicorn）
nohup gunicorn -w 4 -b 0.0.0.0:8000 cloud_platform.server:app > /var/log/fireguard-api.log 2>&1 &

# 验证
curl http://127.0.0.1:8000/healthz
# 应返回 {"code":0,"msg":"ok","db":"up"}
```

### 7. 配置 Nginx（可选，图片公网访问必需）

在 Nginx 配置中新增：

```nginx
# 证据图片静态目录
location /evidence/ {
    alias /data/fireguard/evidence/;
    # 可选：限制只允许 GET
    limit_except GET { deny all; }
}
```

重载 Nginx：
```bash
nginx -t && nginx -s reload
```

验证图片可访问（放一张测试图）：
```bash
echo "test" > /data/fireguard/evidence/test.txt
curl http://127.0.0.1/evidence/test.txt
# 应返回 "test"，然后删掉: rm /data/fireguard/evidence/test.txt
```

---

## 三、接口鉴权说明

### 机制

API 使用简单的 **static token** 鉴权，不是用户登录系统。

```
请求方 → Authorization: Bearer <token> → 云端 API
云端   → 跟 .env 里的 API_TOKEN 比对  → 一致放行 / 不一致 401
```

### 哪些接口需要 token？

| 接口 | 方法 | 鉴权 |
|------|------|------|
| `/healthz` | GET | ❌ 不需要 |
| `/api/v1/evidence` | POST | ✅ 写接口 |
| `/api/v1/fire-alarms` | POST | ✅ 写接口 |
| `/api/v1/fire-alarms` | GET | ✅ 默认需要 |
| `/api/v1/fire-alarms/{id}` | GET | ✅ 默认需要 |

当前实现中读接口也校验 token。如果希望前端无需 token 就能查数据，
可将读接口的 `_require_token()` 检查移除。

### 如何关闭鉴权（开发阶段）

`.env` 中 `API_TOKEN` 设为空即可：

```ini
API_TOKEN=
```

此时所有接口都不校验，车端和前端随意调用。生产环境再设值。

### 如何开启鉴权（生产阶段）

1. 在服务器上生成随机 token：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
# 输出类似: xK3mP9vQ2wR7nL5tY8bE1aF6
```

2. 云端 `.env` 设置：

```ini
API_TOKEN=xK3mP9vQ2wR7nL5tY8bE1aF6
```

3. 车端 `.env` 设置同样的值：

```env
CLOUD_API_TOKEN=xK3mP9vQ2wR7nL5tY8bE1aF6
```

4. 前端调用时带 header：

```javascript
fetch('http://8.140.28.233:8000/api/v1/fire-alarms?page=1&size=20', {
  headers: { 'Authorization': 'Bearer xK3mP9vQ2wR7nL5tY8bE1aF6' }
})
```

5. curl 测试：

```bash
# 不带 token → 401
curl http://8.140.28.233:8000/api/v1/fire-alarms?page=1
# 返回: {"code":401,"msg":"unauthorized"}

# 带 token → 200
curl -H "Authorization: Bearer xK3mP9vQ2wR7nL5tY8bE1aF6" \
  http://8.140.28.233:8000/api/v1/fire-alarms?page=1
# 返回: {"code":0,"msg":"ok","data":{...}}
```

---

## 四、验证 API

部署完成后在服务器上测试：

```bash
TOKEN="<你设的 API_TOKEN>"
BASE="http://127.0.0.1:8000"

# 1. 健康检查
curl $BASE/healthz

# 2. 测试写入一条告警
curl -X POST $BASE/api/v1/fire-alarms \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "deploy_test_001",
    "alarm_type": "confirmed_fire",
    "occurred_at": "2026-07-13T10:00:00+08:00",
    "reason": "部署验证测试",
    "confidence": 0.95,
    "car_id": "test"
  }'

# 应返回: {"code":0,"msg":"ok","id":1,"duplicated":false}

# 3. 查询
curl -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/fire-alarms?page=1&size=5"

# 4. 清理测试数据
mysql -h 127.0.0.1 -u root -p dev_fireguard -e "DELETE FROM fire_alarm WHERE event_id='deploy_test_001';"
```

---

## 五、systemd 服务（推荐，开机自启）

```bash
cat > /etc/systemd/system/fireguard-api.service <<'EOF'
[Unit]
Description=FireGuard Cloud API
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/MiniMover/cloud_platform
EnvironmentFile=/opt/MiniMover/cloud_platform/.env
ExecStart=/usr/bin/gunicorn -w 4 -b 0.0.0.0:8000 cloud_platform.server:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable fireguard-api
systemctl start fireguard-api
systemctl status fireguard-api
```

---

## 六、车端对接

车端（Jetson）在 `fire_smoke_detection/.env` 中追加：

```env
CLOUD_API_BASE_URL=http://8.140.28.233:8000
CLOUD_API_TOKEN=<和云端一模一样的 token>
CAR_ID=car-01
```

启动检测后，告警会自动上报到云端。

---

## 七、供前端展示的读接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/fire-alarms` | GET | 分页查询，参数：`type`, `car_id`, `from`, `to`, `page`, `size` |
| `/api/v1/fire-alarms/{id}` | GET | 单条详情（含 raw_payload） |

前端调用示例：
```javascript
// 查最近 20 条
fetch('http://8.140.28.233:8000/api/v1/fire-alarms?page=1&size=20', {
  headers: { 'Authorization': 'Bearer <API_TOKEN>' }
}).then(r => r.json()).then(console.log)

// 按类型筛选
fetch('http://8.140.28.233:8000/api/v1/fire-alarms?type=confirmed_fire&page=1&size=20', {
  headers: { 'Authorization': 'Bearer <API_TOKEN>' }
}).then(r => r.json()).then(console.log)
```

---

## 八、常用运维

```bash
# 查看日志
journalctl -u fireguard-api -f          # systemd 方式
tail -f /var/log/fireguard-api.log      # nohup 方式

# 重启
systemctl restart fireguard-api

# 数据库直接查告警数量
mysql -h 127.0.0.1 -u root -p dev_fireguard -e "SELECT alarm_type, COUNT(*) FROM fire_alarm GROUP BY alarm_type;"
```
