#!/usr/bin/python3
"""Graba la pose actual del robot (/amcl_pose, marco map) con un nombre en un YAML de ubicaciones.
Mueve el robot (teleop o Nav2), y luego:  ros2 run paper_vla_tb3so101 guardar_ubicacion.py recojo_rojo --archivo ~/ubicaciones.yaml"""
import argparse, math, os, sys
import rclpy, yaml
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('nombre'); ap.add_argument('--archivo', default='ubicaciones.yaml'); a = ap.parse_args()
    rclpy.init(); n = Node('guardar_ubicacion'); got = []
    n.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', got.append, QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
    while not got and rclpy.ok():
        rclpy.spin_once(n, timeout_sec=0.2)
    p = got[0].pose.pose; q = p.orientation
    pose = [round(p.position.x, 3), round(p.position.y, 3), round(math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2)), 3)]
    d = yaml.safe_load(open(a.archivo, encoding='utf-8')) if os.path.exists(a.archivo) else {}
    d = d or {}; d[a.nombre] = pose
    yaml.safe_dump(d, open(a.archivo, 'w', encoding='utf-8'), allow_unicode=True, default_flow_style=None)
    print(f'{a.nombre}: x={pose[0]} y={pose[1]} yaw={pose[2]} -> {a.archivo}')
    rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
