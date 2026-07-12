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

## 接口

| 路径 | 说明 |
|------|------|
| `POST /api/register` | 注册（需 3 张人脸照） |
| `POST /api/login` | 登录 + 人脸拍照校验 |
| `POST /api/logout` | 退出 |
| `GET /api/user/profile/` | 当前用户信息 |
| `POST /api/face_recognition` | 1:N 人脸识别 |
| `POST /api/face_verify_one_to_one/` | 1:1 人脸比对 |

## 密钥

百度云 API 密钥在 `face_auth/baidu_face.py`，AES 密钥在 `face_auth/crypto.py`。
