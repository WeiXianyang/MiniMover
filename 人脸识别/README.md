# 人脸识别服务

基于 Django + 百度云人脸 API 的登录注册与人脸校验模块。

## 启动

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

## 访问

- 演示页面：http://127.0.0.1:8000/api/
- 接口文档：http://127.0.0.1:8000/swagger/

## 1:N 身份识别（识别眼前是谁）

无需登录账号，只要该用户已通过注册接口录入人脸库，即可识别当前画面中的人。

### 网页方式

1. 启动服务后打开 http://127.0.0.1:8000/api/
2. 切到「身份识别」标签
3. 打开摄像头 → 点击「识别此人」
4. 成功时显示：`你是：张三，相似度 95.2 分`

### 本地摄像头脚本（不连小车）

```bash
pip install opencv-python
python identify_camera.py
```

按空格识别当前画面，按 `q` 退出。

### API 调用

```bash
curl -X POST http://127.0.0.1:8000/api/face_recognition \
  -F "image=@photo.jpg"
```

成功响应示例：

```json
{
  "msg": "识别成功",
  "identity": "zhangsan",
  "user": {"id": 1, "username": "zhangsan", "email": "a@b.com", "score": 95.2}
}
```

## 接口

| 路径 | 说明 |
|------|------|
| `POST /api/register` | 注册（需 3 张人脸照） |
| `POST /api/login` | 登录 + 人脸拍照校验 |
| `POST /api/logout` | 退出 |
| `GET /api/user/profile/` | 当前用户信息 |
| `POST /api/face_recognition` | 1:N 身份识别（返回眼前这个人是谁） |
| `POST /api/face_verify_one_to_one/` | 1:1 人脸比对 |

## 密钥

百度云 API 密钥在 `face_auth/baidu_face.py`，AES 密钥在 `face_auth/crypto.py`。
