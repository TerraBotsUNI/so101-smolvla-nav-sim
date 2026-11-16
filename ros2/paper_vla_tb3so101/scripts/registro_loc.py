#!/usr/bin/python3
"""Diagnóstico de localización: cada 0.5 s de simulación guarda la pose que cree AMCL (TF map->base_footprint) y la pose real (Gazebo /gt_tf)
y el error entre ambas; además el rumbo de la odometría de las ruedas y la corrección map->odom de AMCL. Se lanza en paralelo a so101_mision.py. Uso: python3 registro_loc.py <csv>"""
import csv, math, sys, time, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from tf2_msgs.msg import TFMessage
from nav_msgs.msg import Odometry
from tf2_ros import Buffer, TransformListener


def yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


rclpy.init(); n = Node('registro_loc', parameter_overrides=[Parameter('use_sim_time', value=True)])
gt = {}; n.create_subscription(TFMessage, '/gt_tf', lambda m: gt.update({t.child_frame_id: t.transform for t in m.transforms}), 10)
buf = Buffer(); TransformListener(buf, n)
od = {}; n.create_subscription(Odometry, '/odom', lambda m: od.__setitem__('yaw', yaw(m.pose.pose.orientation)), 10)
f = open(sys.argv[1], 'w', newline=''); w = csv.writer(f); w.writerow(['reloj', 't', 'amcl_x', 'amcl_y', 'amcl_yaw', 'real_x', 'real_y', 'real_yaw', 'err_m', 'err_yaw_deg', 'odom_yaw', 'map_odom_yaw'])
t_sig = 0.0
while rclpy.ok():
    rclpy.spin_once(n, timeout_sec=0.05)
    t = n.get_clock().now().nanoseconds * 1e-9
    if t < t_sig or 'tb3_so101' not in gt:
        continue
    t_sig = t + 0.5
    try:
        tr = buf.lookup_transform('map', 'base_footprint', rclpy.time.Time())
        mo = buf.lookup_transform('map', 'odom', rclpy.time.Time())
    except Exception:
        continue
    a, r = tr.transform, gt['tb3_so101']
    ex, ey = a.translation.x - r.translation.x, a.translation.y - r.translation.y
    ey_ = math.degrees(math.remainder(yaw(a.rotation) - yaw(r.rotation), 2 * math.pi))
    w.writerow([time.strftime('%H:%M:%S'), round(t, 2), round(a.translation.x, 3), round(a.translation.y, 3), round(math.degrees(yaw(a.rotation)), 1),
                round(r.translation.x, 3), round(r.translation.y, 3), round(math.degrees(yaw(r.rotation)), 1), round(math.hypot(ex, ey), 3), round(ey_, 1), round(math.degrees(od.get('yaw', 0.0)), 1), round(math.degrees(yaw(mo.transform.rotation)), 1)])
    f.flush()
