import os
import re

from .config import DEFAULT_MAP, MAP_HOST_DIR


def map_paths(map_name=None):
    name = map_name or DEFAULT_MAP
    return {
        'name': name,
        'pgm': os.path.join(MAP_HOST_DIR, f'{name}.pgm'),
        'yaml': os.path.join(MAP_HOST_DIR, f'{name}.yaml'),
    }


def _parse_pgm_header(pgm_bytes):
    """解析 P2/P5 PGM 头，返回 (magic, width, height, maxval, data_offset)。"""
    if not pgm_bytes.startswith(b'P2') and not pgm_bytes.startswith(b'P5'):
        raise ValueError('不是 PGM 文件')
    i = 0
    tokens = []
    n = len(pgm_bytes)
    while i < n and len(tokens) < 4:
        # 跳过空白
        while i < n and pgm_bytes[i:i + 1] in b' \t\r\n':
            i += 1
        if i >= n:
            break
        # 注释
        if pgm_bytes[i:i + 1] == b'#':
            while i < n and pgm_bytes[i:i + 1] not in b'\n\r':
                i += 1
            continue
        start = i
        while i < n and pgm_bytes[i:i + 1] not in b' \t\r\n':
            i += 1
        tokens.append(pgm_bytes[start:i].decode('ascii', errors='ignore'))
    if len(tokens) < 4:
        raise ValueError('PGM 头不完整: %r' % tokens)
    magic = tokens[0]
    width = int(tokens[1])
    height = int(tokens[2])
    maxval = int(tokens[3])
    # 头结束后还有一个空白，数据从下一字节开始
    while i < n and pgm_bytes[i:i + 1] in b' \t\r':
        i += 1
    if i < n and pgm_bytes[i:i + 1] in b'\n':
        i += 1
    return magic, width, height, maxval, i


def load_pgm_gray(path):
    """读取 PGM 为 uint8 numpy 灰度图 (H, W)。"""
    import numpy as np
    with open(path, 'rb') as f:
        pgm_bytes = f.read()
    magic, width, height, maxval, offset = _parse_pgm_header(pgm_bytes)
    if magic == 'P5':
        raw = pgm_bytes[offset:offset + width * height]
        if len(raw) < width * height:
            raise ValueError('PGM 像素数据长度不足')
        img = np.frombuffer(raw, dtype=np.uint8).reshape((height, width)).copy()
    else:
        # P2 ASCII
        vals = [int(x) for x in pgm_bytes[offset:].split()]
        img = np.array(vals[:width * height], dtype=np.uint8).reshape((height, width))
    if maxval != 255 and maxval > 0:
        img = (img.astype('float32') * (255.0 / maxval)).astype('uint8')
    return img


def read_map_info(map_name=None):
    paths = map_paths(map_name)
    info = {
        'map': paths['name'],
        'width': 0,
        'height': 0,
        'resolution': 0.05,
        'origin': [-10.0, -10.0, 0.0],
    }
    if os.path.isfile(paths['yaml']):
        with open(paths['yaml'], 'r', encoding='utf-8') as f:
            yaml_text = f.read()
        res = re.search(r'resolution:\s*([\d.]+)', yaml_text)
        org = re.search(
            r'origin:\s*\[([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\]', yaml_text)
        if res:
            info['resolution'] = float(res.group(1))
        if org:
            info['origin'] = [
                float(org.group(1)), float(org.group(2)), float(org.group(3))]
    if os.path.isfile(paths['pgm']):
        try:
            with open(paths['pgm'], 'rb') as f:
                # 只读头部，避免大地图整文件进内存
                head = f.read(4096)
            _, width, height, _, _ = _parse_pgm_header(head + b'\n')
            info['width'], info['height'] = width, height
        except Exception:
            # 兜底：不抛 500，保持 width/height=0 让前端仍能显示其他信息
            pass
    return info


def pixel_to_map(pixel_x, pixel_y, map_info):
    res = map_info['resolution']
    origin = map_info['origin']
    height = map_info['height']
    x = pixel_x * res + origin[0]
    y = (height - pixel_y) * res + origin[1]
    return round(x, 4), round(y, 4)


def map_to_pixel(map_x, map_y, map_info):
    res = map_info['resolution']
    origin = map_info['origin']
    height = map_info['height']
    pixel_x = (map_x - origin[0]) / res
    pixel_y = height - (map_y - origin[1]) / res
    return round(pixel_x, 2), round(pixel_y, 2)


def screen_to_pixel(screen_x, screen_y, display_w, display_h, map_info):
    map_w = map_info['width']
    map_h = map_info['height']
    if display_w <= 0 or display_h <= 0:
        raise ValueError('display width/height must be positive')
    pixel_x = screen_x * map_w / display_w
    pixel_y = screen_y * map_h / display_h
    return pixel_to_map(pixel_x, pixel_y, map_info)
