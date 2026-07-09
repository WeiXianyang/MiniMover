#!/usr/bin/env python3
""" FireGuard REST API Server """
from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess, threading, time, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sensors.icar_sensor_driver import iCarSensorDriver

app = Flask(__name__)
CORS(app)
sensor = iCarSensorDriver()

CID = subprocess.getoutput('sudo docker ps -q | head -1')

def ros2(cmd):
    if not CID: return
    subprocess.Popen(['docker','exec',CID,'bash','-c',
        'source /root/icar_ros2_ws/icar_ws/install/setup.bash 2>/dev/null || '
        'source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash 2>/dev/null; '
        + cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@app.route('/api/status')
def get_status():
    ip = subprocess.getoutput('hostname -I').split()[0]
    return jsonify({'code':0, 'data':{
        'sensors': sensor.get_data(), 'battery':12.0, 'ip':ip,
        'streams':{'ir':f'http://{ip}:8080/stream_viewer?topic=/camera/ir/image_raw',
                   'depth':f'http://{ip}:8080/stream_viewer?topic=/camera/depth/colorized'}
    }})

@app.route('/api/move', methods=['POST'])
def move():
    data = request.json; cmd = data.get('cmd','stop')
    s = min(data.get('speed',50),100)/100.0; d = data.get('duration',0.5)
    vm = {'forward':(s,0,0),'backward':(-s,0,0),'left':(0,0,s),'right':(0,0,-s),
          'left_shift':(0,s,0),'right_shift':(0,-s,0),'stop':(0,0,0)}
    vx,vy,vz = vm.get(cmd,(0,0,0))
    if cmd!='stop' and d>0:
        ros2(f'ros2 topic pub /cmd_vel geometry_msgs/Twist "{{linear:{{x:{vx},y:{vy},z:0.0}},angular:{{z:{vz}}}}}" --once')
        threading.Thread(target=lambda:(time.sleep(d),
            ros2('ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear:{x:0.0,y:0.0,z:0.0},angular:{z:0.0}}" --once')),
            daemon=True).start()
    else:
        ros2('ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear:{x:0.0,y:0.0,z:0.0},angular:{z:0.0}}" --once')
    return jsonify({'code':0,'msg':f'{cmd} @ {s*100:.0f}%'})

@app.route('/api/camera')
def camera():
    ip = subprocess.getoutput('hostname -I').split()[0]
    return jsonify({'code':0,'streams':{'ir':f'http://{ip}:8080/stream_viewer?topic=/camera/ir/image_raw','depth':f'http://{ip}:8080/stream_viewer?topic=/camera/depth/colorized'}})

@app.route('/api/sensors')
def get_sensors():
    return jsonify({'code':0,'data':sensor.get_data()})

@app.route('/api/health')
def health():
    return jsonify({'code':0,'msg':'FireGuard API Running'})

if __name__=='__main__':
    sensor.start()
    app.run(host='0.0.0.0',port=5000,debug=False,use_reloader=False)
