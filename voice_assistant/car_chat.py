#!/usr/bin/env python3
"""小南 ↔ 小北 自主聊天 —— 本机 LLM 推演，车端 TTS 播放，边走边聊"""

import requests
import time
import random
import os
import sys

# === 车端地址 ===
NAN_IP = "192.168.137.254"
BEI_IP = "192.168.137.23"
API_PORT = 5000

NAN_URL = f"http://{NAN_IP}:{API_PORT}"
BEI_URL = f"http://{BEI_IP}:{API_PORT}"

# === LLM 配置 ===
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_FILE = os.path.join(os.path.dirname(_HERE), ".tts.env")  # MiniMover/.tts.env
if not os.path.exists(_ENV_FILE):
    _ENV_FILE = os.path.join(_HERE, ".tts.env")  # fallback: voice_assistant/.tts.env
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip().strip('"').strip("'"))

import dashscope
dashscope.api_key = os.getenv("MINIMOVER_DASHSCOPE_API_KEY", "")

LLM_MODEL = "qwen-plus"

# === 角色设定 ===
NAN_PERSONA = """你叫小南，是一个友善的男性机器人小车。你性格开朗活泼，喜欢交朋友。
你正在和小北（一个温柔的女性机器人小车）初次见面聊天。
你说的话要短小精悍，一句话不超过20个字，像真人对话一样自然。
可以问对方问题，也可以分享自己。话题围绕互相认识、兴趣爱好。
不要说"作为AI"之类的话，你就是小南。"""

BEI_PERSONA = """你叫小北，是一个温柔的女性机器人小车。你性格文静但很温暖，喜欢帮助别人。
你正在和小南（一个开朗活泼的男性机器人小车）初次见面聊天。
你说的话要短小精悍，一句话不超过20个字，像真人对话一样自然。
可以问对方问题，也可以分享自己。话题围绕互相认识、兴趣爱好。
不要说"作为AI"之类的话，你就是小北。"""

# === 延迟模拟（秒）===
LISTEN_DELAY = (5.0, 5.0)   # 收听延迟（固定5秒）
THINK_DELAY  = (5.0, 5.0)   # 思考延迟（固定5秒）
INTERVAL     = 5.0           # 说完后间隔（固定5秒）

# === 历史记录 ===
history = []
TOTAL_ROUNDS = 8  # 各说8轮


def tts_say(ip, url, text, name):
    """调用车端 TTS"""
    try:
        r = requests.post(f"{url}/api/audio/say", json={"text": text}, timeout=15)
        data = r.json()
        print(f"  [{name}] 🔊 {text}")
        print(f"       TTS: {data.get('msg', r.status_code)}")
        return True
    except Exception as e:
        print(f"  [{name}] TTS 失败: {e}")
        return False


def ask_llm(persona, name, history_tail):
    """让 LLM 生成下一句对话"""
    messages = [{"role": "system", "content": persona}]
    for h in history_tail:
        role = "user" if h["speaker"] != name else "assistant"
        messages.append({"role": role, "content": h["text"]})
    
    # 最后一条是对方说的话，所以当前用户要回复
    messages.append({"role": "user", "content": f"请回复小{'北' if name == '小南' else '南'}刚才的话。你叫{name}，用自然的口语简短回复。"})

    try:
        resp = dashscope.Generation.call(
            model=LLM_MODEL,
            messages=messages,
            result_format="message",
            max_tokens=80,
            temperature=0.9,
        )
        if resp.status_code == 200:
            return resp.output.choices[0].message.content.strip()
        else:
            print(f"  LLM error: {resp.code} {resp.message}")
            return None
    except Exception as e:
        print(f"  LLM exception: {e}")
        return None


def main():
    print("=" * 50)
    print("  小南 ↔ 小北 自主聊天")
    print(f"  小南: {NAN_URL}")
    print(f"  小北: {BEI_URL}")
    print(f"  话题: 互相认识 | 收听: {LISTEN_DELAY[0]}-{LISTEN_DELAY[1]}s | 思考: {THINK_DELAY[0]}-{THINK_DELAY[1]}s | 轮次: {TOTAL_ROUNDS}")
    print("=" * 50)

    if not dashscope.api_key:
        print("❌ 未找到 DashScope API Key，请检查 .tts.env")
        sys.exit(1)

    # === 小南开场 ===
    opener = "你好小北！我是小南，很高兴认识你！"
    history.append({"speaker": "小南", "text": opener})

    print(f"\n--- 开场: 小南 说话 ---")
    think = random.uniform(*THINK_DELAY)
    print(f"  [小南] 🤔 思考中... ({think:.1f}s)", flush=True)
    time.sleep(think)
    tts_say(NAN_IP, NAN_URL, opener, "小南")

    # 小北收听 + 消化
    listen = random.uniform(*LISTEN_DELAY)
    print(f"  [小北] 👂 收听中... ({listen:.1f}s)", flush=True)
    time.sleep(listen)

    current_speaker = "小北"
    round_count = 1

    # === 主循环 ===
    while round_count <= TOTAL_ROUNDS:
        persona = BEI_PERSONA if current_speaker == "小北" else NAN_PERSONA
        speaker_url = BEI_URL if current_speaker == "小北" else NAN_URL
        speaker_ip = BEI_IP if current_speaker == "小北" else NAN_IP

        print(f"\n--- 第 {round_count} 轮: {current_speaker} 说话 ---")

        # 收听延迟
        listen = random.uniform(*LISTEN_DELAY)
        print(f"  [{current_speaker}] 👂 收听中... ({listen:.1f}s)", flush=True)
        time.sleep(listen)

        # 思考延迟
        think = random.uniform(*THINK_DELAY)
        print(f"  [{current_speaker}] 🤔 思考中... ({think:.1f}s)", flush=True)
        time.sleep(think)

        # LLM 生成回复
        reply = ask_llm(persona, current_speaker, history[-6:])
        if not reply:
            reply = "嗯，你说得对。"

        history.append({"speaker": current_speaker, "text": reply})

        # 说话者 TTS 播报
        tts_say(speaker_ip, speaker_url, reply, current_speaker)

        # 间隔
        print(f"  ⏳ 间隔 {INTERVAL}s...", flush=True)
        time.sleep(INTERVAL)

        # 交换说话者
        current_speaker = "小北" if current_speaker == "小南" else "小南"
        round_count += 1

    # === 收尾 ===
    print("\n--- 聊天结束 ---")
    bye_nan = "今天聊得好开心，下次再聊！"
    bye_bei = "嗯嗯，很高兴认识你，再见！"

    tts_say(NAN_IP, NAN_URL, bye_nan, "小南")
    time.sleep(2)
    tts_say(BEI_IP, BEI_URL, bye_bei, "小北")

    print("\n✅ 聊天完成！")


if __name__ == "__main__":
    main()
