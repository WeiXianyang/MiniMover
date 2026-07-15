#!/usr/bin/env python3
# coding:utf-8
"""CLI bridge: JSON stdout for MiniMover backend to call via docker exec."""
import json
import math
import os
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Path
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import SetBool, Trigger
from yahboomcar_patrol_interfaces.srv import GetRoute, SetRoute


class PatrolBridge(Node):
    def __init__(self):
        super().__init__('patrol_api_bridge')
        self._trigger = {
            'start': self.create_client(Trigger, '/patrol/start'),
            'stop': self.create_client(Trigger, '/patrol/stop'),
            'clear': self.create_client(Trigger, '/patrol/clear'),
        }
        self._set_route = self.create_client(SetRoute, '/patrol/set_route')
        self._get_route = self.create_client(GetRoute, '/patrol/get_route')
        self._set_loop = self.create_client(SetBool, '/patrol/set_loop')
        self._initial_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 1)
        self._status_sub = None
        self._last_status = ''

    def _service_name(self, client):
        return getattr(client, 'srv_name', None) or getattr(client, 'service_name', 'unknown')

    def _wait(self, client, timeout=15.0):
        """rclpy 必须 spin 才能发现已有服务"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if client.wait_for_service(timeout_sec=0.5):
                return
            rclpy.spin_once(self, timeout_sec=0.1)
        raise RuntimeError(
            'service unavailable: %s (ROS_DOMAIN_ID=%s, is p1 running?)' % (
                self._service_name(client),
                os.environ.get('ROS_DOMAIN_ID', 'unset')))

    def _call_trigger(self, name):
        self._wait(self._trigger[name])
        req = Trigger.Request()
        future = self._trigger[name].call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=15.0)
        result = future.result()
        if result is None:
            raise RuntimeError('%s call failed' % name)
        return {'success': result.success, 'message': result.message}

    def set_route(self, points):
        self._wait(self._set_route)
        path = Path()
        path.header.frame_id = 'map'
        for pt in points:
            pose = PoseStamped()
            pose.header.frame_id = 'map'
            pose.pose.position.x = float(pt['x'])
            pose.pose.position.y = float(pt['y'])
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)

        req = SetRoute.Request()
        req.route = path
        future = self._set_route.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=15.0)
        result = future.result()
        if result is None:
            raise RuntimeError('set_route call failed')
        return {
            'success': result.success,
            'message': result.message,
            'point_count': result.point_count,
        }

    def get_route(self):
        self._wait(self._get_route)
        req = GetRoute.Request()
        future = self._get_route.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=15.0)
        result = future.result()
        if result is None:
            raise RuntimeError('get_route call failed')
        points = []
        for pose in result.route.poses:
            points.append({
                'x': round(pose.pose.position.x, 4),
                'y': round(pose.pose.position.y, 4),
            })
        return {
            'success': result.success,
            'message': result.message,
            'point_count': result.point_count,
            'patrol_active': result.patrol_active,
            'loop': result.loop,
            'points': points,
        }

    def set_loop(self, enabled):
        self._wait(self._set_loop)
        req = SetBool.Request()
        req.data = bool(enabled)
        future = self._set_loop.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=15.0)
        result = future.result()
        if result is None:
            raise RuntimeError('set_loop call failed')
        return {'success': result.success, 'message': result.message}

    def set_initial_pose(self, x, y, yaw):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = float(x)
        msg.pose.pose.position.y = float(y)
        msg.pose.pose.orientation.z = math.sin(float(yaw) / 2.0)
        msg.pose.pose.orientation.w = math.cos(float(yaw) / 2.0)
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.06853891945200942
        self._initial_pub.publish(msg)
        rclpy.spin_once(self, timeout_sec=0.2)
        return {
            'success': True,
            'message': 'Initial pose set to (%.2f, %.2f, yaw=%.2f)' % (x, y, yaw),
            'x': float(x),
            'y': float(y),
            'yaw': float(yaw),
        }

    def get_status(self, timeout=2.0):
        self._last_status = ''
        self._status_sub = self.create_subscription(
            String, '/patrol_status', self._status_cb, 10)

        end = self.get_clock().now().nanoseconds + int(timeout * 1e9)
        while rclpy.ok() and self.get_clock().now().nanoseconds < end:
            rclpy.spin_once(self, timeout_sec=0.2)
            if self._last_status:
                break

        if self._status_sub:
            self.destroy_subscription(self._status_sub)
            self._status_sub = None

        route = self.get_route()
        return {
            'status': self._last_status or 'unknown',
            'patrol_active': route.get('patrol_active', False),
            'point_count': route.get('point_count', 0),
            'loop': route.get('loop', True),
        }

    def _status_cb(self, msg):
        self._last_status = msg.data


def _parse_points(raw):
    data = json.loads(raw)
    if not isinstance(data, list) or len(data) < 1:
        raise ValueError('points must be a non-empty list')
    points = []
    for item in data:
        if isinstance(item, dict):
            points.append({'x': item['x'], 'y': item['y']})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            points.append({'x': item[0], 'y': item[1]})
        else:
            raise ValueError('invalid point: %r' % item)
    return points


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'usage: patrol_api_bridge <cmd> [args]'}))
        sys.exit(1)

    cmd = sys.argv[1]
    rclpy.init()
    node = PatrolBridge()
    try:
        if cmd == 'start':
            out = node._call_trigger('start')
        elif cmd == 'stop':
            out = node._call_trigger('stop')
        elif cmd == 'clear':
            out = node._call_trigger('clear')
        elif cmd == 'set_route':
            points = _parse_points(sys.argv[2])
            out = node.set_route(points)
        elif cmd == 'get_route':
            out = node.get_route()
        elif cmd == 'status':
            out = node.get_status()
        elif cmd == 'set_loop':
            out = node.set_loop(sys.argv[2].lower() in ('1', 'true', 'yes', 'on'))
        elif cmd == 'set_initial_pose':
            x, y = float(sys.argv[2]), float(sys.argv[3])
            yaw = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
            out = node.set_initial_pose(x, y, yaw)
        else:
            raise ValueError('unknown command: %s' % cmd)
        print(json.dumps(out, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'success': False, 'message': str(exc)}, ensure_ascii=False))
        sys.exit(1)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
