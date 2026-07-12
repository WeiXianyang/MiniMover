"""验证两台新车"""
import requests, sys
API = 'http://localhost:8888'
r = requests.get(f'{API}/api/status', timeout=10)
d = r.json()
print('状态:')
for cid in ['car_A', 'car_B']:
    s = d['cars'].get(cid, {})
    code = s.get('code', '?')
    ip = s.get('data', {}).get('ip', '?') if s.get('code') == 0 else 'N/A'
    bat = s.get('data', {}).get('battery', '?') if s.get('code') == 0 else 'N/A'
    print(f'  {cid}: code={code}, IP={ip}, BAT={bat}V')
print(f'碰撞: {list(d["collisions"].keys()) if d["collisions"] else "无"}')
print(f'面板: http://localhost:8888/dashboard')