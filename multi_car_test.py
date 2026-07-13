#!/usr/bin/env python3
"""多车协同测试：控制真车(5000) + 模拟车(5001)"""
import requests
from concurrent.futures import ThreadPoolExecutor
import time

# ===== 车辆注册表 =====
CARS = {
    'car_A': {'ip': '192.168.137.23', 'port': 5000, 'real': True},
    'car_B': {'ip': '192.168.137.254', 'port': 5000, 'real': True},
}

def api(car_id, endpoint, method='GET', data=None):
    info = CARS[car_id]
    url = f"http://{info['ip']}:{info['port']}{endpoint}"
    try:
        if method == 'GET':
            r = requests.get(url, timeout=3)
        else:
            r = requests.post(url, json=data, timeout=3)
        return r.json()
    except Exception as e:
        return {'code': -1, 'msg': str(e)}

def get_all_status():
    """并行获取所有小车状态"""
    def poll(cid):
        return cid, api(cid, '/api/status')
    with ThreadPoolExecutor(max_workers=len(CARS)) as pool:
        return dict(pool.map(lambda cid: poll(cid), CARS.keys()))

def move_all(cmd, speed=50, duration=0.5):
    """并行控制所有小车"""
    def ctrl(cid):
        return cid, api(cid, '/api/move', 'POST',
                        {'cmd': cmd, 'speed': speed, 'duration': duration})
    with ThreadPoolExecutor(max_workers=len(CARS)) as pool:
        return dict(pool.map(lambda cid: ctrl(cid), CARS.keys()))

if __name__ == '__main__':
    print("=" * 50)
    print("  多车协同测试")
    print("=" * 50)

    # 1. 检查状态
    print("\n[1] 检查所有小车状态...")
    statuses = get_all_status()
    for cid, s in statuses.items():
        if s.get('code') == 0:
            d = s['data']
            print(f"  [OK] {cid}: IP={d.get('ip')}, BAT={d.get('battery')}V")
        else:
            print(f"  [X] {cid}: {s.get('msg', '连接失败')}")

    # 2. 控制测试
    print("\n[2] 同时前进...")
    results = move_all('forward', speed=30, duration=0.5)
    for cid, r in results.items():
        print(f"  {cid}: {r.get('msg', 'OK')}")
    time.sleep(0.6)

    print("\n[3] 再次检查位置...")
    for cid, s in get_all_status().items():
        pos = s.get('data', {}).get('position', 'N/A')
        print(f"  {cid}: position={pos}")

    print("\n[4] 同时停止...")
    results = move_all('stop')
    for cid, r in results.items():
        print(f"  {cid}: {r.get('msg', 'OK')}")

    print("\n[OK] 多车协同测试完成")