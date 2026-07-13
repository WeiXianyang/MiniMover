# MiniMover 中文语音使用说明

本文说明小车当前已验证的中文语音链路：**阿里云百炼 CosyVoice → 小车 USB 音箱**。

## 一、当前配置

| 项目 | 配置 |
|---|---|
| TTS 服务 | 阿里云百炼 DashScope |
| 模型 | `cosyvoice-v3-flash` |
| 音色 | `longanyang` |
| 输出格式 | WAV |
| 云端采样率 | 24000 Hz |
| 播放采样率 | 44100 Hz、双声道 |
| 小车地址 | `192.168.137.254` |
| 音箱 | C-Media USB Audio |
| 音量 | ALSA `PCM 100%` |

`cosyvoice-v3-flash` 是当前使用的低成本模型。代码中保留 `espeak-ng` 作为云端请求失败时的离线回退。

## 二、配置 API Key

在小车上创建权限为 `600` 的配置文件：

```bash
ssh jetson@192.168.137.254
mkdir -p /home/jetson/MiniMover
cat > /home/jetson/MiniMover/.tts.env <<'EOF'
export MINIMOVER_DASHSCOPE_API_KEY="替换为你的阿里云百炼 API Key"
export MINIMOVER_COSYVOICE_MODEL="cosyvoice-v3-flash"
export MINIMOVER_COSYVOICE_VOICE="longanyang"
export MINIMOVER_TTS_PROVIDER="dashscope"
EOF
chmod 600 /home/jetson/MiniMover/.tts.env
```

不要把真实 API Key 提交到 Git、日志或聊天记录中。若 Key 曾经公开，应在阿里云控制台重新生成。

## 三、设置音量

将车载 USB 声卡的硬件音量设置为 100%：

```bash
amixer -c 0 sset PCM 100%
amixer -c 0 sget PCM | tail -4
```

预期看到左右声道均为：

```text
Playback 37 [100%] [0.00dB] [on]
```

程序在云端音频转换阶段使用 `volume=1.8` 软件增益。如果声音失真，可将 `audio/icar_audio.py` 中的 `volume=1.8` 调低到 `1.2` 或 `1.0`。

## 四、直接播放测试

```bash
cd /home/jetson/MiniMover
set -a
. ./.tts.env
set +a
python3 - <<'PY'
from audio.icar_audio import play_wav, say

text = "你好呀，我是你的智能小车，很高兴见到你。"
audio = say(text, "zh")
print("audio bytes:", len(audio))
play_wav(audio)
print("playback started")
PY
```

如果终端编码导致中文变成问号，可使用 Unicode 转义，避免发送无效文本：

```python
text = "\\u4f60\\u597d\\u5440\\uff0c\\u6211\\u662f\\u4f60\\u7684\\u667a\\u80fd\\u5c0f\\u8f66\\uff0c\\u5f88\\u9ad8\\u5174\\u89c1\\u5230\\u4f60\\u3002"
```

## 五、通过车载 API 播放

启动车载 API 后，可以从小车本机或同一局域网设备请求：

```bash
curl -X POST http://127.0.0.1:5000/api/audio/say \
  -H 'Content-Type: application/json' \
  -d '{"text":"你好呀，我是你的智能小车，很高兴为你服务。","lang":"zh"}'
```

成功响应类似：

```json
{"code":0,"msg":"TTS: 你好呀，我是你的智能小车，很高兴为你服务。"}
```

查看音频设备和 TTS 状态：

```bash
curl http://127.0.0.1:5000/api/audio/devices
```

## 六、启动与重启

使用项目现有服务脚本启动：

```bash
cd /home/jetson/MiniMover
bash scripts/start_services.sh
```

如果只需要重启 API，可先确认没有重复进程占用 5000 端口，再启动：

```bash
pids=$(lsof -t -iTCP:5000 -sTCP:LISTEN 2>/dev/null)
for pid in $pids; do kill "$pid"; done
cd /home/jetson/MiniMover
set -a
. ./.tts.env
set +a
nohup python3 api_server.py >/tmp/api.log 2>&1 </dev/null &
```

查看日志：

```bash
tail -f /tmp/api.log
```

## 七、故障排查

### 1. 返回 `Arrearage` 或账号欠费

先在阿里云百炼控制台充值或开通模型服务，再重试。API Key 有效不代表账号已经具备调用额度。

### 2. 返回 `InvalidParameter`

确认请求体使用以下结构，`format` 和 `sample_rate` 放在 `parameters` 中：

```json
{
  "model": "cosyvoice-v3-flash",
  "input": {
    "text": "你好，我是小车。",
    "voice": "longanyang"
  },
  "parameters": {
    "format": "wav",
    "sample_rate": 24000
  }
}
```

### 3. 播放的是机械音

说明云端 TTS 请求失败并触发了 `espeak-ng` 回退。检查：

- `.tts.env` 是否被 `source`；
- `MINIMOVER_TTS_PROVIDER` 是否为 `dashscope`；
- API Key 是否有效且账号有余额；
- `/tmp/api.log` 中是否出现 `DashScope TTS unavailable`。

### 4. 音量仍然偏小

依次确认：

```bash
amixer -c 0 sget PCM | tail -4
pactl list short sinks
```

同时确认播放设备是代码中的 `USB_SINK`，不要误播到 HDMI 或系统默认声卡。

### 5. SSH 连接不稳定

当前小车使用：

```bash
ssh jetson@192.168.137.254
```

如果 Paramiko 偶尔出现 `Error reading SSH protocol banner`，通常是小车 SSH 握手队列暂时繁忙；等待几秒后重试，不要同时创建大量 SSH 连接。
