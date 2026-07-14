import ast
import re


def parse_baidu_user_info(user_info):
    """从百度云 user_info 字段解析显示名。"""
    if not user_info:
        return None
    if isinstance(user_info, dict):
        return user_info.get('username') or user_info.get('name') or user_info.get('user_id')

    text = str(user_info).strip()
    try:
        data = ast.literal_eval(text)
        if isinstance(data, dict):
            return data.get('username') or data.get('name') or data.get('user_id')
    except (SyntaxError, ValueError):
        pass

    match = re.search(r"'username'\s*:\s*'([^']+)'", text)
    if match:
        return match.group(1)
    return text or None


def resolve_display_name(identified, local_username=None):
    """优先本地用户名，否则用百度云 user_info，最后退回 user_id。"""
    if local_username:
        return local_username
    name = parse_baidu_user_info(identified.get('user_info'))
    if name:
        return str(name)
    user_id = identified.get('user_id')
    if user_id is not None:
        return f'user_{user_id}'
    return 'unknown'


def overlay_display_name(identified, local_username=None):
    """OpenCV overlay text: ASCII only, avoid ??? for non-Latin names."""
    name = resolve_display_name(identified, local_username=local_username)
    if name and all(ord(c) < 128 for c in str(name)):
        return str(name)
    user_id = identified.get('user_id')
    return f'user_{user_id}' if user_id is not None else 'unknown'


def overlay_error_lines(msg, score=None):
    """Map API errors to English lines for on-screen display."""
    text = msg or 'Unknown error'
    if '未找到匹配' in text:
        lines = ['Identify failed', 'No match in face library']
    elif '相似度不足' in text:
        lines = ['Identify failed', 'Score below threshold']
    elif '没有人脸' in text:
        lines = ['Identify failed', 'No face detected']
    elif '无法解析' in text or '质量' in text:
        lines = ['Identify failed', 'Poor image quality']
    elif '暂不可用' in text:
        lines = ['Identify failed', 'Face API unavailable']
    else:
        lines = ['Identify failed', 'See console for details']
    if score is not None:
        lines.append(f'score={score:.1f}')
    return lines

