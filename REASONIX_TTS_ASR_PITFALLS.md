# 🚨 TTS & ASR 避坑指南 — 必读！

> **触发规则**: 任何智能体在处理"音频播放""TTS""语音合成""ASR""语音识别""麦克风""扬声器""百炼 DashScope"相关任务时，**必须**完整阅读本文，否则将重蹈覆辙。

---

## 一、环境概况

| 组件 | 位置 | 说明 |
|------|------|------|
| Jetson 小车 | `192.168.202.171`, 用户 `jetson` | ARM Ubuntu；认证使用 SSH 密钥或本地凭据，不在仓库记录密码 |
| PC 控制台 | `192.168.202.222`, Windows | GPU ASR 模型 (RTX 4060) |
| 麦克风 | Jetson `hw:2,0` (XFM-DP-V0.0.18) | 16kHz mono |
| USB 扬声器 | Jetson ALSA card 0 (C-Media USB Audio) | **只支持立体声 44.1kHz** |
| API Key | 百炼 DashScope `sk-ws-...` | 新平台密钥，必须配合 WorkspaceId |

---

## 二、TTS 播放 ⚠️ 最容易踩坑

### ❌ 错误做法

```python
# 1. 用 REST API 直接调 dashscope.aliyuncs.com —— sk-ws- 密钥不支持！
requests.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/text2speech/speech-synthesis", ...)
# → 400 "url error"

# 2. 用 paplay 播放 —— systemd 进程没有 PulseAudio！
subprocess.run(["paplay", "output.wav"])
# → 静默失败，无声音

# 3. 用 aplay -D hw:0,0 播单声道 WAV —— C-Media 声卡拒绝单声道！
subprocess.run(["aplay", "-D", "hw:0,0", "mono.wav"])
# → "Channels count non available"

# 4. 用 AudioFormat.WAV —— 不存在！
format=AudioFormat.WAV
# → AttributeError

# 5. SpeechSynthesizer.call(model=...) —— 参数名不对！
SpeechSynthesizer.call(model='cosyvoice-v3-flash', text='你好')
# → "unexpected keyword argument 'model'"
```

### ✅ 正确做法

```python
import os
from dashscope.audio.tts_v2 import SpeechSynthesizer
from dashscope.audio.tts_v2.speech_synthesizer import AudioFormat

# 1. 设置环境变量（必须！）
api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("MINIMOVER_DASHSCOPE_API_KEY")
workspace_id = os.environ.get("DASHSCOPE_WORKSPACE_ID") or os.environ.get("MINIMOVER_DASHSCOPE_WORKSPACE_ID")
if not api_key or not workspace_id:
    raise RuntimeError("请先在本地环境文件中配置 DashScope 凭据")
os.environ["DASHSCOPE_API_KEY"] = api_key
os.environ["DASHSCOPE_WORKSPACE_ID"] = workspace_id

# 2. 构造合成器（model 和 voice 在 __init__ 传，不在 call 传）
syn = SpeechSynthesizer(
    model="cosyvoice-v3-flash",
    voice="longanhuan",
    format=AudioFormat.WAV_16000HZ_MONO_16BIT,  # ← 枚举值，不是字符串
)

# 3. call() 只传 text，返回 bytes（不是 result 对象！）
wav_bytes = syn.call(text="你好世界")

# 4. 保存并播放 —— 必须用 plughw（不是 hw），因为声卡需要格式转换
with open("/tmp/tts.wav", "wb") as f:
    f.write(wav_bytes)
subprocess.run(["aplay", "-D", "plughw:0,0", "-q", "/tmp/tts.wav"])
```

### 关键点

| 问题 | 答案 |
|------|------|
| `sk-ws-` 密钥的端点 | `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/...` |
| WorkspaceId | 从本地环境变量读取（在百炼控制台 → 业务空间管理 获取），不要硬编码到仓库 |
| 为什么不能用 `dashscope.aliyuncs.com` | 那是旧版 DashScope 的域名，`sk-ws-` 密钥只认 workspace 域名 |
| 播放方式 | `aplay -D plughw:0,0`（**不是** paplay，**不是** hw:0,0） |
| systemd 下能播吗 | 能！`jetson` 用户在 `audio` 组中，ALSA 有权限 |
| 默认音频输出 | 是 Jetson 内置声卡 (`platform-sound`)，**不是** USB 喇叭！ |
| USB 声卡编号 | `card 0` (C-Media USB Audio)，用 `aplay -l` 确认 |
| 声卡只支持立体声 | 必须用 `plughw` 自动转换（mono→stereo, rate 适配） |
| 音色 | `longanhuan`, `longanyang`, `longanchu` 等 |
| SDK 版本 | `dashscope>=1.26.3` |

---

## 三、ASR 语音识别

### 当前方案
- **PC 端本地 FunASR Paraformer 流式识别** (RTX 4060 CUDA)
- Jetson 麦克风音频 → WebSocket → PC → 返回文本

### 已知问题
- 流式模式对短句容易**幻觉**（如 "你好小北" → "小北好小北"）
- 修复：`pc_asr_server.py` 中 `is_final=True` 时做二阶段非流式补识别

---

## 四、环境变量加载

### 文件与格式

| 文件 | 格式 | 谁加载 |
|------|------|--------|
| `.env.voice` | `KEY=VALUE` | `api_server.py` 启动时 + systemd EnvironmentFile |
| `.tts.env` | `export KEY=VALUE` | `icar_audio.py` 的 `_load_tts_env()` |

### 注意
- systemd 的 `EnvironmentFile` **只加载 `.env.voice`**，不加载 `.tts.env`
- `api_server.py` 在 Flask 启动**之前**手动加载两个文件到 `os.environ`
- 环境变量加载顺序：`.env.voice` → `.tts.env`，先到的不覆盖
- **新的 TTS Key 必须在 `.env.voice` 中设置**，`.tts.env` 中的旧 key 会被 `.env.voice` 覆盖

---

## 五、SSH 连接

```bash
ssh jetson@192.168.202.171   # 建议使用 SSH 密钥认证
```

从 Python：
```python
import os
import paramiko

c = paramiko.SSHClient()
c.load_system_host_keys()
c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect(
    "192.168.202.171",
    username="jetson",
    key_filename=os.environ.get("JETSON_SSH_KEY"),
    timeout=10,
)
```

或用 Windows OpenSSH + askpass。

---

## 六、服务管理

| 服务 | 命令 |
|------|------|
| 重启 API | `sudo systemctl restart fireguard-api.service` |
| 查看日志 | `sudo journalctl -u fireguard-api.service --no-pager -n 50` |
| 启动 car_client | `cd ~/MiniMover && source .env.voice && nohup .venv-voice-cpu/bin/python3 -u voice_assistant/car_client.py > /tmp/minimover-hospital-guide-car.log 2>&1 &` |
| 查看 car 日志 | `tail -f /tmp/minimover-hospital-guide-car.log` |
| 测试 TTS | `curl -s -X POST http://127.0.0.1:5000/api/audio/say -H 'Content-Type: application/json' -d '{"text":"测试"}'` |

---

## 七、检查清单

在修改 TTS/ASR/音频相关代码后，逐项确认：

- [ ] TTS 用的是 DashScope SDK (`SpeechSynthesizer`) 而非 REST API
- [ ] `format=` 用的是 `AudioFormat.WAV_16000HZ_MONO_16BIT` 枚举
- [ ] 播放用的是 `aplay -D plughw:0,0` 而非 `paplay`
- [ ] API Key 已写入 `.env.voice`（不是只写在 `.tts.env`）
- [ ] `DASHSCOPE_WORKSPACE_ID` 已设置
- [ ] systemd 重启后 `journalctl` 无异常
- [ ] `curl /api/audio/say` 返回 200 且能听到声音
- [ ] **car_client 中 TTS 播放时暂停麦克风（`_tts_playing` 标志位），防回声死循环**

---

## 八、回声自触发问题

### 现象
TTS 播放的语音被麦克风拾取 → ASR 识别 → 再次触发 LLM → 再次 TTS → 死循环

### 根因
扬声器和麦克风同时工作，没有互斥。

### 正确方案（car_client 端）
TTS 播放时**完全暂停**音频发送，播放完毕再恢复：

```python
_tts_playing = [False]

def _speak(text):
    _tts_playing[0] = True
    try:
        requests.post(url, json={"text": text})  # 同步调用，返回时已播完
    finally:
        _tts_playing[0] = False

def _audio_cb(indata, frames, timestamp, status):
    if _tts_playing[0]:
        return  # 暂停麦克风
    ws.send_binary(...)
```

### ❌ 不要做的事
- 时间估算静音（不准）
- PC 端 `tts_mute_until` 过滤（PC 不掌握播放时长）
- 依赖 VAD 区分回声和真人（Silero VAD 区分力有限）
