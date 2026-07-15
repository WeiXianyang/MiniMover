#!/usr/bin/env python3
# coding:utf-8
"""Publish /initialpose repeatedly until AMCL creates map->odom TF."""
import math

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener


class InitialPoseSetter(Node):
    def __init__(self):
        super().__init__('initial_pose_setter')
        self.declare_parameter('x', 0.0)
        self.declare_parameter('y', 0.0)
        self.declare_parameter('yaw', 0.0)
        self.declare_parameter('start_delay', 8.0)
        self.declare_parameter('retry_interval', 3.0)
        self.declare_parameter('max_retries', 10)

        self._pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 1)
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._retries = 0
        self._done = False
        self._start_delay = self.get_parameter('start_delay').value
        self._max_retries = self.get_parameter('max_retries').value
        self._start_time = self.get_clock().now()

        interval = self.get_parameter('retry_interval').value
        self.create_timer(interval, self._timer_cb)

    def _map_tf_ready(self):
        try:
            self._tf_buffer.lookup_transform('map', 'odom', rclpy.time.Time())
            return True
        except Exception:
            return False

    def _timer_cb(self):
        if self._done:
            return

        elapsed = (self.get_clock().now() - self._start_time).nanoseconds / 1e9
        if elapsed < self._start_delay:
            return

        if self._map_tf_ready():
            self.get_logger().info('map->odom TF ready')
            self._done = True
            return

        if self._retries >= self._max_retries:
            if self._retries == self._max_retries:
                self.get_logger().warn(
                    'map->odom TF still missing; use RViz 2D Pose Estimate or pinit'
                )
                self._retries += 1
            return

        x = self.get_parameter('x').value
        y = self.get_parameter('y').value
        yaw = self.get_parameter('yaw').value

        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.06853891945200942

        self._pub.publish(msg)
        self._retries += 1
        self.get_logger().info(
            'Published initial pose #%d at (%.2f, %.2f)' % (self._retries, x, y)
        )


def main():
    rclpy.init()
    node = InitialPoseSetter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
