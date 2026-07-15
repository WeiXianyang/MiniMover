#!/usr/bin/env python3
# coding:utf-8
"""
RViz route patrol node.

Draw a patrol route in RViz with the "Publish Point" tool, then start patrol.
Each waypoint is reached via navigate_to_pose (same as n3 single-point nav).
"""
import math

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PointStamped, PoseStamped, Quaternion
from nav_msgs.msg import Path
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import SetBool, Trigger
from visualization_msgs.msg import Marker, MarkerArray
from yahboomcar_patrol_interfaces.srv import GetRoute, SetRoute


def yaw_to_quaternion(yaw):
    return Quaternion(x=0.0, y=0.0, z=math.sin(yaw * 0.5), w=math.cos(yaw * 0.5))


def densify_route(points, spacing):
    """Insert waypoints along straight segments at a fixed spacing."""
    if len(points) < 2:
        return list(points)

    waypoints = []
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            continue

        if not waypoints:
            waypoints.append((x1, y1))

        steps = max(1, int(math.floor(dist / spacing)))
        for step in range(1, steps + 1):
            t = min(step * spacing / dist, 1.0)
            waypoints.append((x1 + dx * t, y1 + dy * t))

        if waypoints[-1] != (x2, y2):
            waypoints.append((x2, y2))

    return waypoints


class RoutePatrol(Node):
    def __init__(self):
        super().__init__('route_patrol')

        self.declare_parameter('waypoint_spacing', 0.5)
        self.declare_parameter('loop', True)
        self.declare_parameter('frame_id', 'map')

        self.waypoint_spacing = self.get_parameter('waypoint_spacing').value
        self.loop = self.get_parameter('loop').value
        self.frame_id = self.get_parameter('frame_id').value

        self.route_points = []
        self.patrol_poses = []
        self.patrol_active = False
        self._goal_handle = None
        self._current_index = 0

        self.create_subscription(PointStamped, '/clicked_point', self._clicked_point_cb, 10)
        self.route_pub = self.create_publisher(Path, '/patrol_route', 10)
        self.waypoints_pub = self.create_publisher(MarkerArray, '/waypoints', 10)
        self.status_pub = self.create_publisher(String, '/patrol_status', 10)

        self.create_service(Trigger, '/patrol/start', self._start_cb)
        self.create_service(Trigger, '/patrol/stop', self._stop_cb)
        self.create_service(Trigger, '/patrol/clear', self._clear_cb)
        self.create_service(Trigger, '/patrol/undo', self._undo_cb)
        self.create_service(SetBool, '/patrol/set_loop', self._set_loop_cb)
        self.create_service(SetRoute, '/patrol/set_route', self._set_route_cb)
        self.create_service(GetRoute, '/patrol/get_route', self._get_route_cb)

        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        self._publish_status(
            'ready: RViz Publish Point 画路线, 然后 pstart 开始巡逻'
        )
        self.get_logger().info('Route patrol ready (navigate_to_pose mode, same as n3)')

    def _publish_status(self, text):
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)
        self.get_logger().info(text)

    def _clicked_point_cb(self, msg):
        if self.patrol_active:
            self.get_logger().warn('Patrol running, ignoring new point (stop first)')
            return

        self.route_points.append((msg.point.x, msg.point.y))
        self._publish_route_visuals()
        self._publish_status(
            'route point #%d: (%.2f, %.2f)' % (
                len(self.route_points), msg.point.x, msg.point.y)
        )

    def _publish_route_visuals(self):
        now = self.get_clock().now().to_msg()

        route_path = Path()
        route_path.header.stamp = now
        route_path.header.frame_id = self.frame_id
        for x, y in self.route_points:
            pose = PoseStamped()
            pose.header.stamp = now
            pose.header.frame_id = self.frame_id
            pose.pose.position.x = x
            pose.pose.position.y = y
            pose.pose.orientation.w = 1.0
            route_path.poses.append(pose)
        self.route_pub.publish(route_path)

        markers = MarkerArray()
        for idx, (x, y) in enumerate(self.route_points):
            marker = Marker()
            marker.header.stamp = now
            marker.header.frame_id = self.frame_id
            marker.ns = 'patrol_route'
            marker.id = idx
            marker.type = Marker.SPHERE
            marker.action = Marker.ADD
            marker.pose.position.x = x
            marker.pose.position.y = y
            marker.pose.position.z = 0.1
            marker.pose.orientation.w = 1.0
            marker.scale.x = 0.15
            marker.scale.y = 0.15
            marker.scale.z = 0.15
            marker.color.r = 1.0
            marker.color.g = 0.4
            marker.color.b = 0.0
            marker.color.a = 1.0
            markers.markers.append(marker)
        self.waypoints_pub.publish(markers)

    def _delete_marker_namespace(self, ns):
        now = self.get_clock().now().to_msg()
        delete_all = Marker()
        delete_all.header.stamp = now
        delete_all.header.frame_id = self.frame_id
        delete_all.ns = ns
        delete_all.action = Marker.DELETEALL
        self.waypoints_pub.publish(MarkerArray(markers=[delete_all]))

    def _clear_route_visuals(self):
        now = self.get_clock().now().to_msg()
        self._delete_marker_namespace('patrol_route')
        self._delete_marker_namespace('patrol_waypoints')

        empty_path = Path()
        empty_path.header.stamp = now
        empty_path.header.frame_id = self.frame_id
        self.route_pub.publish(empty_path)

    def _build_patrol_poses(self):
        dense_points = densify_route(self.route_points, self.waypoint_spacing)
        if len(dense_points) < 1:
            return []

        poses = []
        for idx, (x, y) in enumerate(dense_points):
            pose = PoseStamped()
            pose.header.frame_id = self.frame_id
            pose.pose.position.x = x
            pose.pose.position.y = y

            if idx < len(dense_points) - 1:
                nx, ny = dense_points[idx + 1]
                yaw = math.atan2(ny - y, nx - x)
            elif len(dense_points) >= 2:
                px, py = dense_points[idx - 1]
                yaw = math.atan2(y - py, x - px)
            else:
                yaw = 0.0

            pose.pose.orientation = yaw_to_quaternion(yaw)
            poses.append(pose)

        return poses

    def _publish_patrol_waypoints(self, poses):
        now = self.get_clock().now().to_msg()
        markers = MarkerArray()

        for idx, pose in enumerate(poses):
            marker = Marker()
            marker.header.stamp = now
            marker.header.frame_id = self.frame_id
            marker.ns = 'patrol_waypoints'
            marker.id = idx
            marker.type = Marker.ARROW
            marker.action = Marker.ADD
            marker.pose = pose.pose
            marker.pose.position.z = 0.05
            marker.scale.x = 0.35
            marker.scale.y = 0.08
            marker.scale.z = 0.08
            marker.color.r = 0.0
            marker.color.g = 0.8
            marker.color.b = 1.0
            marker.color.a = 0.9
            markers.markers.append(marker)

        self.waypoints_pub.publish(markers)

    def _start_cb(self, request, response):
        del request
        if len(self.route_points) < 2:
            response.success = False
            response.message = 'Need at least 2 route points (use Publish Point in RViz)'
            self._publish_status(response.message)
            return response

        self.patrol_poses = self._build_patrol_poses()
        if not self.patrol_poses:
            response.success = False
            response.message = 'Failed to generate patrol waypoints'
            self._publish_status(response.message)
            return response

        self._publish_patrol_waypoints(self.patrol_poses)
        self.patrol_active = True
        self._current_index = 0
        self._send_next_goal()
        response.success = True
        response.message = 'Patrol started with %d waypoints' % len(self.patrol_poses)
        self._publish_status(response.message)
        return response

    def _send_next_goal(self):
        if not self.patrol_active:
            return

        if self._current_index >= len(self.patrol_poses):
            if self.loop:
                self._publish_status('Route done, looping patrol')
                self._current_index = 0
            else:
                self.patrol_active = False
                self._goal_handle = None
                self._publish_status('Patrol route completed')
                return

        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.patrol_active = False
            self._publish_status('navigate_to_pose not available (is p1 running?)')
            return

        pose = self.patrol_poses[self._current_index]
        pose.header.stamp = self.get_clock().now().to_msg()

        goal = NavigateToPose.Goal()
        goal.pose = pose

        self._publish_status(
            'navigating to waypoint %d / %d' % (
                self._current_index + 1, len(self.patrol_poses))
        )

        send_future = self._action_client.send_goal_async(goal)
        send_future.add_done_callback(self._goal_response_cb)

    def _goal_response_cb(self, future):
        self._goal_handle = future.result()
        if not self._goal_handle.accepted:
            self.patrol_active = False
            self._publish_status('Navigation goal rejected')
            return

        result_future = self._goal_handle.get_result_async()
        result_future.add_done_callback(self._result_cb)

    def _result_cb(self, future):
        if not self.patrol_active:
            return

        status = future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self._current_index += 1
            self._send_next_goal()
        elif status == GoalStatus.STATUS_CANCELED:
            self._publish_status('Patrol canceled')
        else:
            self.patrol_active = False
            self._publish_status('Navigation failed at waypoint %d' % (self._current_index + 1))

    def _stop_cb(self, request, response):
        del request
        self.patrol_active = False
        if self._goal_handle is not None:
            cancel_future = self._goal_handle.cancel_goal_async()
            cancel_future.add_done_callback(
                lambda f: self._publish_status('Patrol stopped'))
        else:
            self._publish_status('Patrol stopped')
        response.success = True
        response.message = 'Patrol stopped'
        return response

    def _clear_cb(self, request, response):
        del request
        if self.patrol_active:
            response.success = False
            response.message = 'Stop patrol before clearing route'
            return response

        self.route_points = []
        self.patrol_poses = []
        self._current_index = 0
        self._clear_route_visuals()
        response.success = True
        response.message = 'Route cleared'
        self._publish_status(response.message)
        return response

    def _undo_cb(self, request, response):
        del request
        if self.patrol_active:
            response.success = False
            response.message = 'Stop patrol before editing route'
            return response
        if not self.route_points:
            response.success = False
            response.message = 'No route points to undo'
            return response

        removed = self.route_points.pop()
        self._publish_route_visuals()
        response.success = True
        response.message = 'Removed point (%.2f, %.2f)' % removed
        self._publish_status(response.message)
        return response

    def _points_to_path(self, points):
        now = self.get_clock().now().to_msg()
        route_path = Path()
        route_path.header.stamp = now
        route_path.header.frame_id = self.frame_id
        for x, y in points:
            pose = PoseStamped()
            pose.header.stamp = now
            pose.header.frame_id = self.frame_id
            pose.pose.position.x = x
            pose.pose.position.y = y
            pose.pose.orientation.w = 1.0
            route_path.poses.append(pose)
        return route_path

    def _path_to_points(self, route):
        points = []
        for pose in route.poses:
            points.append((pose.pose.position.x, pose.pose.position.y))
        return points

    def _set_route_cb(self, request, response):
        if self.patrol_active:
            response.success = False
            response.message = 'Stop patrol before setting route'
            response.point_count = len(self.route_points)
            return response

        points = self._path_to_points(request.route)
        if len(points) < 1:
            response.success = False
            response.message = 'Need at least 1 route point'
            response.point_count = 0
            self._publish_status(response.message)
            return response

        self.route_points = points
        self.patrol_poses = []
        self._current_index = 0
        self._publish_route_visuals()
        response.success = True
        response.message = 'Route set with %d points' % len(points)
        response.point_count = len(points)
        self._publish_status(response.message)
        return response

    def _get_route_cb(self, request, response):
        del request
        response.success = True
        response.route = self._points_to_path(self.route_points)
        response.point_count = len(self.route_points)
        response.patrol_active = self.patrol_active
        response.loop = self.loop
        response.message = 'Route has %d points, patrol_active=%s' % (
            response.point_count, self.patrol_active)
        return response

    def _set_loop_cb(self, request, response):
        self.loop = request.data
        response.success = True
        response.message = 'Loop patrol: %s' % ('ON' if self.loop else 'OFF')
        self._publish_status(response.message)
        return response


def main():
    rclpy.init()
    node = RoutePatrol()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
