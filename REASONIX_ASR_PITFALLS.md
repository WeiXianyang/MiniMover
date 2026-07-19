# ASR 语音识别避坑指南

> **适用项目**: MiniMover 医院导诊语音助手
> **重要性**: ⚠️ 任何涉及 ASR 录制、TTS 播放的智能体**必须先读本文**
> **关联文档**: `REASONIX_TTS_ASR_PITFALLS.md`（TTS 播放避坑）

---

## 一、架构原则

### 端边结合
- **PC 端**（Windows, RTX 4060）：ASR 语音识别 + VAD + 唤醒词检测
- **Jetson 端**（小车）：麦克风采集 → WebSocket 发送音频 → 接收 ASR 结果 → 调用 LLM + TTS → 扬声器播放

### 为什么不用本地 FunASR
| 指标 | FunASR 本地 | 百炼 DashScope API |
|------|------------|-------------------|
| 显存 | **1.5 GB** | **0** |
| 启动时间 | **2 分钟** | **2 秒** |
| 识别延迟 | ~500ms | ~600-800ms |
| 准确度 | 一般（短句常错） | **好** |
| 维护成本 | 高（模型更新、GPU 驱动） | **零** |

**结论：永远不要用本地 FunASR。**

---

## 二、DashScope 百炼 ASR API 正确用法

### ⚠️ 2.0 环境变量名陷阱 — 最高优先级！

**DashScope SDK 只认 `DASHSCOPE_API_KEY`，不认任何带前缀的名字！**

```python
# ❌ 错误：SDK 读不到这个 key，所有 ASR 调用静默返回空字符串！
os.environ["MINIMOVER_DASHSCOPE_API_KEY"] = "sk-..."

# ✅ 正确：必须同时设置 SDK 需要的名字
os.environ["DASHSCOPE_API_KEY"] = os.environ.get("MINIMOVER_DASHSCOPE_API_KEY", "")
```

**现象：** ASR 返回空 `""`，没有任何报错，日志里 `result (xxxms): '' sentences=None`，让人误以为音频质量有问题。**花了数小时调 VAD、增益、音频格式，根本原因就是 key 名字不匹配。**

### 2.1 API Key 类型
`sk-ws-*` 开头的 key **不是** OpenAI 兼容 key，必须配合 `workspace` 参数。
`sk-076-*` 开头的 key 是常规 key，不需要 workspace。

```python
# ❌ 错误：用 OpenAI 兼容端点
# POST https://dashscope.aliyuncs.com/compatible-mode/v1/audio/transcriptions

# ✅ 正确：用 DashScope 原生 SDK
import os
os.environ["DASHSCOPE_API_KEY"] = os.environ.get("MINIMOVER_DASHSCOPE_API_KEY", "")  # ← 关键！

from dashscope.audio.asr import Recognition, RecognitionCallback

rec = Recognition(
    model="paraformer-realtime-v2",
    callback=callback,
    format="wav",
    sample_rate=16000,
    workspace="ws-xxxxxxxxxxxxx",  # sk-ws-* 必须！sk-076-* 不需要
)
```

### 2.2 Recognition.call() 陷阱

**最大的坑**: `RecognitionCallback.on_event()` **只在 streaming 模式触发**，`call(file=...)` 是同步文件模式，**不触发回调**！

```python
# ❌ 错误：回调不会触发
cb = MyCallback()
rec = Recognition(callback=cb, ...)
rec.call(file="audio.wav")
text = " ".join(cb.texts)  # ← 永远是空的！

# ✅ 正确：从返回值拿结果
result = rec.call(file="audio.wav")
sentences = result.get_sentence()  # ← 返回 list[dict]
text = ""
for s in (sentences or []):
    text += s.get("text", "")
```

### 2.3 完整示例

```python
import os, wave
import numpy as np

os.environ["DASHSCOPE_API_KEY"] = "sk-ws-..."
WORKSPACE = "ws-xxxxxxxxxxxxx"

def asr_pcm(pcm_samples: np.ndarray) -> str:
    """将 int16 PCM 数组转为 WAV 文件，调用百炼 ASR"""
    from dashscope.audio.asr import Recognition, RecognitionCallback

    class _CB(RecognitionCallback):
        def on_event(self, result): pass  # 文件模式不触发

    cb = _CB()

    # 写临时 WAV
    import tempfile
    wav_path = tempfile.mktemp(suffix=".wav")
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm_samples.astype(np.int16).tobytes())

    try:
        rec = Recognition(
            model="paraformer-realtime-v2",
            callback=cb,
            format="wav",
            sample_rate=16000,
            workspace=WORKSPACE,
        )
        result = rec.call(file=wav_path)
        sentences = result.get_sentence() or []
        return "".join(s.get("text", "") for s in sentences)
    finally:
        os.unlink(wav_path)
```

---

## 三、VAD（语音活动检测）

### 必须保留 VAD
即使 ASR 换成百炼 API，**Silero VAD 仍然需要**：
- 检测语音开始/结束
- 分割音频为独立句子
- 只在语音结束时调用 ASR API（节省费用）

### VAD 参数
```python
SAMPLE_RATE = 16000
BLOCK_MS = 200              # 200ms 一个块
MIN_SPEECH_MS = 300         # 最短语音
SILENCE_GAP_MS = 800        # 静音间隔（判定句子结束）
```

---

## 四、TTS 回声问题 ← 最重要！

### 问题
TTS 播放的声音被麦克风拾取 → ASR 识别 → 再次触发对话 → 死循环

### ❌ 错误方案（时间估算静音）
```python
# 估算播放时长然后 mute —— 不可靠！时长估不准，回声照样漏
est_dur = max(1.5, len(text) / 3.5 + 1.0)
_speak_mute_until = time.time() + est_dur
```

### ✅ 正确方案（播放期间完全暂停麦克风）
TTS 播放时麦克风**完全不发送**音频到 PC，播放完毕再恢复：

```python
_tts_playing = [False]  # list 用于跨线程访问

def _speak(text):
    _tts_playing[0] = True
    try:
        r = requests.post(f"{CAR_URL}/api/audio/say", json={"text": text})
    finally:
        _tts_playing[0] = False  # API 返回 = 播放完毕

def _audio_cb(indata, frames, timestamp, status):
    if _tts_playing[0]:
        return  # 暂停麦克风
    ws.send_binary(indata.tobytes())
```

**关键点：** `requests.post` 是同步调用，TTS API 返回时音频已播放完毕。利用这一点天然同步"TTS结束=恢复麦克风"。

### ⚠️ 不要做的事
- 不要用时间估算（`est_dur = len(text) / N`）——不准
- 不要在 PC 端设 `tts_mute_until` 来过滤——PC 端不知道何时播完
- 不要依赖 VAD 过滤回声——Silero VAD 对扬声器回声区分能力有限

---

## 五、SSH 连接陷阱

### paramiko exec_command 杀后台进程
```python
# ❌ exec_command 返回后会关闭 SSH 通道 → 后台进程被杀
client.exec_command("nohup python car_client.py &")

# ✅ 用 invoke_shell() 保持会话
shell = client.invoke_shell()
shell.send("nohup python car_client.py &\n")
time.sleep(3)
shell.close()
```

### Windows taskkill 权限
```python
# ❌ 在 bash/git-bash 中 Windows 命令斜杠会被转义
# 用 Python subprocess（list 参数）避免转义
subprocess.run(["taskkill", "/F", "/PID", str(pid)])
```

---

## 六、唤醒词匹配

### 模糊拼音匹配
```python
from pypinyin import lazy_pinyin

def _fuzzy_pinyin(text):
    p = "".join(lazy_pinyin(text)).lower()
    # 卷舌→平舌
    for a, b in [("zh","z"), ("ch","c"), ("sh","s")]:
        p = p.replace(a, b)
    # 前后鼻音
    for a, b in [("ing","in"), ("eng","en")]:
        p = p.replace(a, b)
    return p

wake_word = "你好小北"
if _fuzzy_pinyin(wake_word) in _fuzzy_pinyin(asr_text):
    print("WAKE!")
```

---

## 七、环境变量配置 —— ⚠️ 最高频踩坑！

### ✅ 正确方案：pc_asr_server.py 自己加载
不要在 shell / launcher 里加载 env，**让 `pc_asr_server.py` 在 import 时自己读 `.env.voice` + `.tts.env`**。

代码已内置在文件头部（`# ═══ 自己加载 .env.* — 永远不依赖外部环境 ═══`），零外部依赖。

### 必设的环境变量（放在 `.env.voice`）
| 变量 | 用途 |
|------|------|
| `MINIMOVER_DASHSCOPE_API_KEY` | 百炼 API Key |
| `MINIMOVER_DASHSCOPE_WORKSPACE_ID` | 百炼 Workspace ID |

### ❌ 禁止做的事
- 不要在 bash 里 `export` 然后启动——env 不会传递
- 不要用 `launch_asr.py` 加载 env——多一层就多一个出错点
- 不要依赖 `launch_asr.py`——它的 env 加载和 pc_asr_server 自己加载互相覆盖

---

## 八、端口管理

- **8765**: 旧 FunASR 端口（已废弃，但老的 PowerShell 进程可能占用且杀不掉）
- **8766**: 新 DashScope ASR 端口（当前使用）
- **5000**: Jetson API 服务器端口

### 端口被占用
```bash
# 查端口
netstat -ano | findstr ":8766"
# Windows 杀不掉 PID（Access Denied）→ 换端口
```

---

## 九、常见故障排查

| 现象 | 可能原因 | 解决 |
|------|---------|------|
| ASR 没反应 | car_client 死了 | SSH 重启 car_client |
| ASR 返回空 | API key/workspace 错误 | 检查 `.env.voice` |
| ASR 识别乱码 | 麦克风采到噪音 | 检查 RMS > 500 |
| TTS 播放中断 | 回声打断 | 检查 `_speak_mute_until` |
| car_client 连不上 | PC ASR 端口不对 | 检查 `MINIMOVER_ASR_PORT` |
| "导诊服务暂不可用" | LLM API 不通 | curl 测试 `/api/hospital-guide/turn` |

---

## 十、启动顺序

```
1. PC:   python voice_assistant/pc_asr_server.py 8766   （后台运行）
2. Jetson:  sudo systemctl start fireguard-api.service   （API 服务器）
3. Jetson:  source .env.voice && python car_client.py    （语音客户端）
4. 说"你好小北"唤醒
```

---

## 十一、医院导诊免唤醒模式

### 原理
医院导诊场景不需要唤醒词——病人直接问就行。PC 端 `hospital_guide_mode=True` 时：
- **第一句话自动接入**（AUTO-ENGAGE），不需要"你好小北"
- 所有后续语音直接转发给 LLM

### ⚠️ AUTO-ENGAGE 必须同时发 wake_detected + final_text

```python
if hospital_guide_mode and not is_awake:
    # ❌ 错误：只发 wake_detected，car_client 收到唤醒但没收到文本
    await _send_status("wake_detected", text=text)

    # ✅ 正确：同时发两个消息
    await _send_status("wake_detected", text=text)
    await _send_status("final_text", text=text, uid=uid, speaker_sim=1.0, speaker_ok=True)
```

### 短字符过滤
启动 beep、环境噪音产生的 1-2 字符识别结果要跳过：
```python
if len(text.strip()) <= 1:
    print("skip short", file=sys.stderr, flush=True)
```

---

## 十二、bash 后台作业陷阱

### 多个进程不要放同一行 &
```bash
# ❌ 错误：一个死了全死
cmd1 & cmd2 & wait

# ✅ 正确：分别启动独立后台作业
# 启动 ASR 服务器（作业1）
python pc_asr_server.py 8766 &
# 等 10 秒确认 Ready 后，再启动 HTTP 服务器（作业2）
python -m http.server 8767 &
```

### 不要用 process_request 托管 HTTP
`websockets.serve(process_request=...)` API 不稳定，直接启动独立的 `python -m http.server` 托管静态页面。

---

## 十三、变量改名后检查所有引用

修改 `_speak_mute_until` → `_tts_playing` 时，`_audio_cb` 闭包里的旧引用没改导致 `NameError`。

**规则：** 改名后用 `grep` 确认旧名不再出现：
```bash
grep -n "旧变量名" car_client.py
```

---

## 十四、LLM 结果回传面板

car_client 通过 WebSocket 发送 JSON 消息回 PC：
```python
ws.send(json.dumps({"type": "llm_reply", "query": query, "reply": reply}))
```
PC 端在 `handle_car` 的消息处理器中接收并广播给所有 monitor。

---

**最后更新**: 2026-07-16
**教训**: TTS 期间暂停麦克风 > 时间估算静音；bash 后台进程分开启动；改名后 grep 检查。
