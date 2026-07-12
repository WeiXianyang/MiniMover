"""多车协同快速测试"""
import requests, time

API = 'http://localhost:8888'

def test(name, fn):
    try:
        fn()
        print(f'[OK] {name}')
    except Exception as e:
        print(f'[FAIL] {name}: {e}')

# 1. 状态查询
def test_status():
    r = requests.get(f'{API}/api/status', timeout=5)
    d = r.json()
    assert d['code'] == 0
    assert 'car_A' in d['cars']
    assert 'car_B' in d['cars']
    assert 'car_C' in d['cars']

# 2. 全部前进
def test_move_all():
    r = requests.post(f'{API}/api/move_all', json={'cmd': 'forward', 'speed': 30}, timeout=5)
    assert r.json()['code'] == 0

# 3. 编队
def test_formation():
    r = requests.post(f'{API}/api/formation',
                      json={'type': 'line', 'spacing': 2.0, 'car_ids': ['car_B', 'car_C']},
                      timeout=5)
    d = r.json()
    assert d['code'] == 0
    assert 'car_B' in d['targets']
    assert 'car_C' in d['targets']

# 4. 导航单辆车
def test_navigate():
    r = requests.post(f'{API}/api/navigate',
                      json={'car_ids': ['car_B'], 'x': 5, 'y': 0, 'theta': 0},
                      timeout=5)
    assert r.json()['code'] == 0

# 5. 注册新车
def test_register():
    r = requests.post(f'{API}/api/register',
                      json={'car_id': 'car_D', 'ip': '10.0.0.1', 'port': 5000},
                      timeout=5)
    assert r.json()['code'] == 0

# 6. 批量注册
def test_register_batch():
    r = requests.post(f'{API}/api/register_batch',
                      json={'cars': {'car_E': {'ip': '10.0.0.2', 'port': 5000},
                                     'car_F': {'ip': '10.0.0.3', 'port': 5000}}},
                      timeout=5)
    assert r.json()['code'] == 0

print('=== Multi-Car Coordinator Test ===')
test('Status poll (3 cars)', test_status)
test('Move all forward', test_move_all)
test('Line formation B+C', test_formation)
test('Navigate car_B', test_navigate)
test('Register car_D', test_register)
test('Batch register E+F', test_register_batch)

# 最后检查碰撞检测
r = requests.get(f'{API}/api/status', timeout=5)
d = r.json()
print(f'\nCars: {list(d["cars"].keys())}')
print(f'Collisions: {list(d["collisions"].keys()) if d["collisions"] else "none"}')
print('\nDone. Dashboard at http://localhost:8888/dashboard')