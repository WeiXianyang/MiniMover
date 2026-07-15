import ast
import re


def parse_baidu_user_info(user_info):
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
    if local_username:
        return local_username
    name = parse_baidu_user_info(identified.get('user_info'))
    if name:
        return str(name)
    user_id = identified.get('user_id')
    if user_id is not None:
        return f'user_{user_id}'
    return 'unknown'
