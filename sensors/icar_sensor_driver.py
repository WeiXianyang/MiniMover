#!/usr/bin/env python3
"""iCar IoT 传感器驱动"""
import serial, time, struct, threading

SENSOR_TYPES = {
    0x01: 'temperature', 0x02: 'humidity', 0x03: 'smoke',
    0x04: 'pm25', 0x05: 'pressure', 0x06: 'light',
    0x07: 'gps_lat', 0x08: 'gps_lon', 0x09: 'co2',
}

class iCarSensorDriver:
    def __init__(self, port='/dev/ttyUSB2', baud=115200):
        self.port, self.baud = port, baud
        self.ser, self.running = None, False
        self.data = {'temperature':25.0,'humidity':50.0,'smoke':0,'pm25':0,
                     'pressure':1013,'light':500,'co2':400,'gps':{'lat':0,'lon':0}}
        self.lock = threading.Lock()

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.5)
            print(f'[传感器] {self.port} 已打开')
            return True
        except Exception as e:
            print(f'[传感器] 打开失败: {e}')
            return False

    def parse(self, data):
        if len(data)<6 or data[0]!=0xA5: return None
        val = struct.unpack('<H', bytes(data[3:5]))[0]
        cs = (0xA5+data[1]+data[2]+(val&0xFF)+((val>>8)&0xFF))&0xFF
        if cs != data[5]: return None
        return {'node':data[1], 'name':SENSOR_TYPES.get(data[2],f'unk_{data[2]:02x}'), 'value':val}

    def update(self, p):
        with self.lock:
            n, v = p['name'], p['value']
            if n=='temperature': self.data['temperature']=v/10.0
            elif n=='humidity': self.data['humidity']=v/10.0
            elif n=='smoke': self.data['smoke']=v
            elif n=='pm25': self.data['pm25']=v
            elif n=='pressure': self.data['pressure']=v/10.0
            elif n=='light': self.data['light']=v
            elif n=='gps_lat': self.data['gps']['lat']=v/1000000.0
            elif n=='gps_lon': self.data['gps']['lon']=v/1000000.0
            elif n=='co2': self.data['co2']=v

    def read_loop(self):
        while self.running and self.ser:
            try:
                if self.ser.in_waiting>=6:
                    p=self.parse(self.ser.read(6))
                    if p: self.update(p)
                else: time.sleep(0.02)
            except: time.sleep(0.5)

    def start(self):
        if not self.connect(): return False
        self.running=True
        threading.Thread(target=self.read_loop, daemon=True).start()
        print('[传感器] 已启动'); return True

    def stop(self):
        self.running=False
        if self.ser: self.ser.close()

    def get_data(self):
        with self.lock: return dict(self.data)

if __name__=='__main__':
    d=iCarSensorDriver()
    if d.start():
        print('=== 传感器数据 ===')
        try:
            while True:
                data=d.get_data()
                print(f'温度:{data["temperature"]:.1f}°C 湿度:{data["humidity"]:.1f}% 烟雾:{data["smoke"]} PM2.5:{data["pm25"]} 气压:{data["pressure"]:.0f}hPa 光照:{data["light"]} GPS:{data["gps"]["lat"]:.4f},{data["gps"]["lon"]:.4f}')
                time.sleep(2)
        except KeyboardInterrupt: d.stop()
    else: print('传感器启动失败')
