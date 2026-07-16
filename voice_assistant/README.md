# MiniMover 语音助手

基于 FunASR Paraformer 的离线唤醒词语音控制系统，支持唤醒词检测、运动指令解析、LLM 问答和 TTS 语音反馈。

## 整体链路

```text
USB 麦克风 → FunASR (Paraformer + VAD + 标点) → 唤醒词门控 → 指令解析 / LLM → 小车 /api/move
                                                   ↓                            ↘ 小车 /api/audio/say (TTS)
                                              "你好小南" → TTS 打招呼
```

| 模块 | 文件 | 说明 |
|------|------|------|
| ASR 后端 | `asr_backend.py` | FunASR Paraformer 离线识别，支持 Whisper 远程兜底 |
| 唤醒词 | `wake_word.py` | IDLE 状态下扫描唤醒词，命中后切 AWAKE 并 TTS 打招呼 |
| 指令解析 | `command_parser.py` | 中文运动指令 → `{cmd, value}` 结构化输出 |
| LLM 客户端 | `llm_client.py` | OpenAI 兼容接口，处理非运动类语音 |
| TTS 后端 | `tts_backend.py` | 走小车 `api_server.py` 的 `/api/audio/say`，底层用 edge-tts |
| 声纹验证 | `speaker_verifier.py` | CAM++ 说话人验证，拦截未授权运动指令 |
| 配置 | `config.py` | 全部通过环境变量注入 |

---

## 环境要求

- **硬件**：Jetson (L4T R35+)，讯飞 USB 麦克风，C-Media USB 扬声器
- **Python**：3.8+
- **小车 api_server**：已在 5000 端口运行（含 `/api/move` 和 `/api/audio/say`）

### Python 依赖

```bash
pip install funasr torch torchaudio sounddevice silero-vad soundfile edge-tts
```

> 项目自带的 `requirements-voice.txt` 是早期的非完整清单，以实际安装为准。

### FunASR 模型

模型缓存路径：`~/.cache/modelscope/hub/models/`

| 模型 | 大小 | 用途 |
|------|------|------|
| `paraformer-large-vad-punc` | ~868 MB | 离线识别（含 VAD + 标点） |
| `paraformer-large-online` | ~849 MB | 流式识别 |
| `fsmn-vad` | ~4 MB | 独立 VAD |
| `ct-punc` | ~1.2 GB | 标点恢复 |
| `campplus` | ~50 MB | 声纹模型（说话人验证用） |

---

## 快速启动

### 1. 确保小车 API 服务运行

```bash
cd ~/MiniMover
pgrep -f api_server.py || nohup python3 api_server.py > /tmp/api_server.log 2>&1 &
```

验证：
```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/api/audio/say \
  -X POST -H "Content-Type: application/json" -d '{"text":"测试"}'
# 应返回 200
```

### 2. 加载环境配置

项目在 `~/MiniMover/.env.voice` 中已预置了每台小车的配置：

**小南 (254)：**
```
MINIMOVER_WAKE_WORD=你好小南
MINIMOVER_WAKE_GREETING=你好，我是小南，有什么可以帮你的？
MINIMOVER_WAKE_TIMEOUT=30
MINIMOVER_CAR_SPEAKER=1
MINIMOVER_CAR_URL=http://127.0.0.1:5000
MINIMOVER_ASR_BACKEND=funasr
```

**小北 (23)：**
```
MINIMOVER_WAKE_WORD=你好小北
MINIMOVER_WAKE_GREETING=你好，我是小北，有什么可以帮你的？
MINIMOVER_WAKE_TIMEOUT=30
MINIMOVER_CAR_SPEAKER=1
MINIMOVER_CAR_URL=http://127.0.0.1:5000
MINIMOVER_ASR_BACKEND=funasr
```

```bash
# 加载配置
cd ~/MiniMover
set -a; source .env.voice; set +a
```

### 3. 启动语音服务

```bash
# 小南 (254) — CUDA torch venv
.venv-voice/bin/python -m voice_assistant.voice_service

# 小北 (23) — CPU torch venv
.venv-voice-cpu/bin/python -m voice_assistant.voice_service
```

---

## 唤醒词工作流

```text
                    ┌─────────────────────────────────┐
                    │          IDLE（常态）             │
                    │  只扫描唤醒词，忽略所有其他语音    │
                    └──────────────┬──────────────────┘
                                   │ 识别到 "你好小南"
                                   ▼
                    ┌─────────────────────────────────┐
                    │         ⏰ 唤醒                  │
                    │  TTS 播放: "你好，我是小南，      │
                    │  有什么可以帮你的？"              │
                    └──────────────┬──────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────┐
                    │      AWAKE（活跃窗口 30 秒）      │
                    │  处理运动指令 / LLM 问答          │
                    │  每次交互重置 30 秒倒计时          │
                    └──────────────┬──────────────────┘
                                   │ 30 秒无交互
                                   ▼
                    ┌─────────────────────────────────┐
                    │       ⏰ 退回 IDLE               │
                    └─────────────────────────────────┘
```

**要点：**
- AWAKE 状态下每次有效语音都会重置倒计时，连续对话不会意外断开
- 唤醒词只需包含在话中即可触发，例如 "你好小南，往前走" 会同时唤醒并执行指令
- `MINIMOVER_WAKE_TIMEOUT` 可调整活跃窗口时长（默认 30 秒）

---

## 运动指令参考

| 口语示例 | 解析指令 | 效果 |
|----------|----------|------|
| 前进 / 往前走 | `{cmd: "forward"}` | 前进一段距离 |
| 后退 / 往后退 | `{cmd: "backward"}` | 后退一段距离 |
| 左转 / 向左转 | `{cmd: "turn_left"}` | 左转一定角度 |
| 右转 / 向右转 | `{cmd: "turn_right"}` | 右转一定角度 |
| 停止 / 停 | `{cmd: "stop"}` | 紧急停止（最高优先级） |

> 停止指令始终执行，无需声纹验证。

---

## 声纹验证（可选）

启用后，运动指令需要说话人与已注册声纹匹配（余弦相似度 ≥ 0.38）。

### 注册声纹

```bash
python3 -m voice_assistant.speaker_verifier ~/.minimover/speaker_profile.npy
# 对着话筒朗读 15 秒，按 Ctrl+C 结束
```

### 启用声纹门控

```bash
python3 -m voice_assistant.voice_service \
  --speaker-profile ~/.minimover/speaker_profile.npy
```

---

## LLM 问答（可选）

当语音不匹配任何运动指令时，如果有 LLM 配置则走问答模式。

```bash
export MINIMOVER_LLM_URL=https://your-endpoint/v1
export MINIMOVER_LLM_MODEL=gpt-4o-mini
export MINIMOVER_API_KEY=sk-xxx
```

问答结果通过 TTS 语音朗读。

---

## Hospital-guide defense template

The hospital-guide template is enabled by default. Motion commands keep their existing priority: for example, a stop command still goes directly to the vehicle controller, and only non-motion utterances enter the guide conversation. Short-term memory and a pending destination are reset at the start of a wake-word session and when the AWAKE window expires.

This feature is for defense demonstrations only. It provides department routing, in-building directions, and general health education; it **does not diagnose, prescribe, adjust medication, or replace on-site clinicians**. For emergency clues such as unconsciousness, heavy bleeding, or breathing difficulty, it tells the user to contact on-site staff or go to emergency care and never starts navigation automatically.

### 1. Download the pinned local medical knowledge snapshot

From the repository root, run:

```bash
python scripts/fetch_shortmedkg.py
```

The downloader retrieves a fixed ShortMedKG Git commit, validates the JSONL, atomically writes `voice_assistant/data/shortmedkg/input_v4.jsonl`, and creates checksum metadata beside it. The snapshot and metadata are ignored by Git: never commit them, API keys, recordings, or conversation data.

### 2. Bind departments to existing floor-map waypoints

Edit `voice_assistant/data/hospital_guide_template.json`. For each department you will demonstrate, select `x`, `y`, and `theta` with the existing floor-model/map waypoint tool, manually verify the result, and set `navigation.enabled` to `true`.

```json
"navigation": {"enabled": true, "x": 1.25, "y": -3.40, "theta": 0.0}
```

All template departments start with `navigation.enabled: false` and placeholder `0.0` coordinates. **Never use the default `0.0, 0.0, 0.0` as a valid waypoint.** A disabled department never calls `/api/navigate`. The robot asks for an explicit confirmation before it sends any configured destination to navigation.

### 3. Configure the existing OpenAI-compatible LLM and start

The guide uses the existing OpenAI-compatible LLM settings. With no LLM configured, direct department routing and confirmation can still be demonstrated; symptom questions safely fall back to asking the user to consult the service desk.

```bash
export MINIMOVER_LLM_URL=https://your-endpoint/v1
export MINIMOVER_LLM_MODEL=your-model
export MINIMOVER_API_KEY=your-secret
export MINIMOVER_HOSPITAL_GUIDE_ENABLED=1
python -m voice_assistant.voice_service
```

| Variable | Default | Purpose |
|------|--------|------|
| `MINIMOVER_HOSPITAL_GUIDE_ENABLED` | `1` | Set to `0` or `false` to disable guide orchestration. |
| `MINIMOVER_HOSPITAL_GUIDE_PATH` | bundled template | Department and manually reviewed map-waypoint configuration. |
| `MINIMOVER_MEDICAL_KB_PATH` | local ShortMedKG JSONL | Local lightweight retrieval corpus. |
| `MINIMOVER_MEDICAL_MEMORY_TURNS` | `6` | Conversation turns retained, clamped to 1-12. |
| `MINIMOVER_MEDICAL_RETRIEVAL_LIMIT` | `3` | Evidence snippets per turn, clamped to 1-5. |
| `MINIMOVER_MEDICAL_REPLY_MAX_CHARS` | `180` | Reply length before TTS, clamped to 60-300. |

### Demonstration and privacy boundary

This is not for real diagnosis, treatment, or emergency rescue. Ensure on-site staff are available during a defense demonstration. Do not collect or persist names, IDs, medical-record numbers, contact information, recordings, or conversation logs. The current version does not cancel a navigation goal that has already been sent to the navigation stack: a voice stop command retains only its existing chassis-control priority.


## 医院导诊控制台

当 `MINIMOVER_HOSPITAL_GUIDE_ENABLED=1` 的语音服务已启动时，在小车同一局域网中打开：

```text
http://<小车IP>:5000/hospital-guide
```

页面实时展示以下已发生的语音导诊流程：

- 对话记忆、本轮知识库命中数量、急症提示和流程审计；
- 待确认科室、导航是否已下发及结果；
- 已配置的科室点位启用状态（不展示坐标）。

这是一个**只读展示页**：它不提供网页端下发导航的接口，仍只有语音会话中科室已匹配且用户明确说“好的 / 确认”后，才能调用导航。

配置实际科室点位时，请在现有的地图建模选点控制台中进行：

```text
http://<小车IP>:5000/nav/patrol
```

将已核对的点位填入 `voice_assistant/data/hospital_guide_template.json` 后，再将相应科室的 `navigation.enabled` 设为 `true`。任何使用默认 `0.0, 0.0, 0.0` 的点位都不应启用导航。


---

## 远程 Whisper 兜底

当 FunASR 不可用时，可切换为通过小车麦克风录制后发送到远程 Whisper：

```bash
export MINIMOVER_ASR_BACKEND=remote_whisper
export MINIMOVER_WHISPER_URL=https://your-endpoint/v1
export MINIMOVER_API_KEY=sk-xxx
export MINIMOVER_CAR_AUDIO_DURATION=4
python -m voice_assistant.voice_service --asr remote_whisper
```

---

## 全部环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MINIMOVER_WAKE_WORD` | (空，禁用) | 唤醒词，如 `你好小南` |
| `MINIMOVER_WAKE_GREETING` | (自动生成) | 唤醒后 TTS 问候语 |
| `MINIMOVER_WAKE_TIMEOUT` | `30` | AWAKE 窗口超时秒数 |
| `MINIMOVER_CAR_URL` | `http://127.0.0.1:5000` | 小车 API 地址 |
| `MINIMOVER_CAR_SPEAKER` | `0` | `1` 表示用小车扬声器播放 TTS |
| `MINIMOVER_ASR_BACKEND` | `auto` | `funasr` / `whisper` / `remote_whisper` |
| `MINIMOVER_VOICE_SPEED` | `35` | 运动速度 (0-100) |
| `MINIMOVER_VOICE_DURATION` | `0.8` | 单次运动持续秒数 |
| `MINIMOVER_LLM_URL` | (空) | LLM API 地址 |
| `MINIMOVER_LLM_MODEL` | (空) | LLM 模型名 |
| `MINIMOVER_TTS_URL` | (空) | 远程 TTS 地址（非小车模式） |
| `MINIMOVER_TTS_VOICE` | `alloy` | TTS 音色 |
| `MINIMOVER_API_KEY` | (空) | API Key |
| `MINIMOVER_WHISPER_URL` | (空) | Whisper API 地址 |
| `MINIMOVER_CAR_AUDIO_DURATION` | `4` | 远程 Whisper 录制秒数 |
| `MINIMOVER_HOSPITAL_GUIDE_ENABLED` | `1` | Enable hospital-guide orchestration |
| `MINIMOVER_HOSPITAL_GUIDE_PATH` | bundled template | Department and reviewed map-waypoint configuration |
| `MINIMOVER_MEDICAL_KB_PATH` | local ShortMedKG path | Local medical-knowledge JSONL |
| `MINIMOVER_MEDICAL_MEMORY_TURNS` | `6` | Guide memory turns (1-12) |
| `MINIMOVER_MEDICAL_RETRIEVAL_LIMIT` | `3` | Local evidence count (1-5) |
| `MINIMOVER_MEDICAL_REPLY_MAX_CHARS` | `180` | Guide reply length (60-300) |
| `MINIMOVER_HOSPITAL_GUIDE_TELEMETRY_PATH` | guide data directory | Read-only dashboard runtime snapshot path |

---

## 故障排查

| 现象 | 可能原因 | 检查命令 |
|------|----------|----------|
| 唤醒没反应 | 模型路径不对 | `ls ~/.cache/modelscope/hub/models/` |
| TTS 没声音 | api_server 未运行 | `curl http://127.0.0.1:5000/api/audio/say` |
| TTS 返回 500 | edge-tts 未装 | `python3 -c "import edge_tts"` |
| 麦克风无输入 | 设备权限 | `arecord -l` 确认 `hw:2,0` 存在 |
| torch 导入失败 | venv 路径错误 | 确认用的 `.venv-voice` 或 `.venv-voice-cpu` |

## Live hospital-guide voice bridge

Set `MINIMOVER_HOSPITAL_GUIDE_MODE=1` together with `MINIMOVER_HOSPITAL_GUIDE_ENABLED=1` on the Jetson. The live chain is: car microphone and wake word -> WebSocket ASR `final_text` -> local `/api/hospital-guide/turn` -> ShortMedKG retrieval plus an OpenAI-compatible LLM -> the existing car TTS endpoint. In hospital-guide mode, the Jetson client ignores legacy upstream `chat_reply` and `command` messages so they cannot duplicate speech or bypass confirmation-gated navigation.

Fetch the pinned open medical corpus before starting the service:

```bash
python3 scripts/fetch_shortmedkg.py
```

Optional LLM variables are `MINIMOVER_HOSPITAL_GUIDE_LLM_URL`, `MINIMOVER_HOSPITAL_GUIDE_LLM_MODEL`, and `MINIMOVER_HOSPITAL_GUIDE_LLM_API_KEY`. If URL is omitted but a DashScope/API key is present, the bridge uses the DashScope OpenAI-compatible endpoint with `qwen-plus`. If the LLM is unavailable, the bridge falls back to a conservative answer based on the retrieved corpus; it does not diagnose or prescribe.
