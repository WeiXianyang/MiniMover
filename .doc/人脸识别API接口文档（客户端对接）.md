# MiniMover 人脸识别 API（客户端对接）

小车 IP 记为 `<CAR_IP>`（本车常见为 `192.168.137.23`，以 `hostname -I` 为准）。  
人脸服务挂在车端 **`:5000`**，与控制面板、导航接口同一进程——**客户端只需对接这一个端口**。

## 一键启动（车端）

```bash
bash ~/MiniMover/scripts/start_all.sh
```

该命令会启动：

| 能力 | 地址 |
|------|------|
| 控制面板（移动+视频） | `http://<CAR_IP>:5000/` |
| 导航 API / 巡逻页 | `http://<CAR_IP>:5000/nav/patrol` ，接口前缀 `/api/nav/*` |
| 人脸注册网页 | `http://<CAR_IP>:5000/face` |
| 人脸 1:N 识别接口 | `POST http://<CAR_IP>:5000/api/face/recognize` |

等价兼容入口：`bash ~/MiniMover/scripts/start_services.sh`（内部就是 `start_all.sh`）。

> 不需要再单独起控制面板；导航轻量启动 `start_nav_api.sh` 也会带上同一套 API（只是不开相机视频）。

---

## 数据存哪里

| 内容 | 位置 |
|------|------|
| 用户账号、本地人脸照片 | **小车本地**（SQLite + `人脸识别/media/face_images/`） |
| 人脸特征库（1:N 检索） | **百度云人脸库**（group: `user_faces`） |

先在网页注册人脸，再给客户端调识别接口。

注册页（浏览器打开小车摄像头录入）：

```
http://<CAR_IP>:5000/face
```

---

## 客户端必接：1:N 身份识别

识别「眼前是谁」，返回身份 + 置信度。

### 请求

```
POST http://<CAR_IP>:5000/api/face/recognize
Content-Type: multipart/form-data
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `image` | file | 是 | 现场人脸 JPEG/PNG（字段名也可用 `face_image`） |

兼容旧路径（行为相同）：

```
POST http://<CAR_IP>:5000/api/face_recognition
```

### 成功响应 `200`

```json
{
  "ok": true,
  "msg": "识别成功",
  "identity": "zhangsan",
  "score": 95.2,
  "confidence": 0.952,
  "user": {
    "id": "12",
    "username": "zhangsan",
    "email": "a@b.com",
    "score": 95.2,
    "confidence": 0.952,
    "user_info": "{'username': 'zhangsan', 'email': 'a@b.com'}",
    "source": "local_db"
  },
  "candidates": [
    {"group_id": "user_faces", "user_id": "12", "user_info": "...", "score": 95.2}
  ]
}
```

| 字段 | 说明 |
|------|------|
| `identity` | **识别出的人名/账号**（客户端展示用这个） |
| `score` | 百度相似度 **0~100**，也可当作置信度分 |
| `confidence` | 归一化置信度 **0~1**（`score / 100`） |
| `user.id` | 人脸库用户 ID |
| `candidates` | 候选列表（可选展示） |

建议判定：`ok == true` 且 `score >= 80`（服务端默认阈值 80，低于阈值会直接失败）。

### 失败响应

未匹配 / 置信度不足 / 无此人脸：

```json
{
  "ok": false,
  "msg": "未找到匹配用户",
  "error_code": 222207
}
```

或：

```json
{
  "ok": false,
  "msg": "相似度不足（72.3 < 80），无法确认身份",
  "score": 72.3,
  "confidence": 0.723
}
```

常见 HTTP 状态：`400` 业务失败，`404` 库中无人脸匹配，`500` 服务异常。

### curl 示例

```bash
curl -X POST "http://<CAR_IP>:5000/api/face/recognize" \
  -F "image=@photo.jpg"
```

### 伪代码

```text
POST multipart: image=<摄像头抓拍JPEG>
if response.ok and response.identity:
    显示 姓名=response.identity, 置信度=response.score  # 或 response.confidence
else:
    提示 response.msg
```

---

## 可选：网页 / 接口注册人脸

### 网页（推荐运维录入）

打开 `http://<CAR_IP>:5000/face` →「注册」→ 拍 **3 张** 不同角度 → 提交。  
成功后特征同步到百度云，之后客户端即可 1:N 识别。

### 接口注册

```
POST http://<CAR_IP>:5000/api/face/register
Content-Type: multipart/form-data
```

| 字段 | 说明 |
|------|------|
| `username` | 用户名 |
| `password` | 密码 |
| `email` | 邮箱 |
| `phone` | 手机号 |
| `face_images` | 至少 3 张人脸图（同名字段重复多次） |

成功 `201`：

```json
{"ok": true, "msg": "注册成功", "user": {"id": 1, "username": "zhangsan", "faces": 3}}
```

---

## 与其它车端接口的关系

| 服务 | 端口 | 说明 |
|------|------|------|
| 控制 + 导航 + 人脸 | **5000** | 客户端接小车时统一用这个 |
| ROS 视频流 | 8080 | 可选拉流；识别一般由客户端自己拍照上传 |
| 多车总控（PC） | 8888 | 与人脸无关 |

导航接口文档见同目录：`导航巡逻API接口文档.md`。
