#!/usr/bin/python3
"""Compara la cinemática directa propia (so101_kinematics.fk) con el TF real de Gazebo (base_footprint -> gripper_frame_link) en varias poses.
Requiere la simulación lanzada en el mismo dominio/partición. Uso: python3 verificar_fk.py"""
import os, sys, time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from tf2_ros import Buffer, TransformListener
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from so101_kinematics import fk, JOINTS

POSES = [[0, 0, 0, 0, 0], [0.3, -0.5, 0.6, 0.3, 0.0], [-0.4, 0.4, 0.8, -0.2, 0.5], [0.0, 0.8, 0.6, 0.3, 0.0], [0.6, -1.0, 1.2, 0.5, -0.8], [0.0, -1.7, 1.6, 1.1, 0.0]]

rclpy.init(); n = Node('verif_fk', parameter_overrides=[Parameter('use_sim_time', value=True)])
buf = Buffer(); TransformListener(buf, n); js = {}
n.create_subscription(JointState, '/joint_states', lambda m: js.update(zip(m.name, m.position)), 10)
pub = n.create_publisher(JointTrajectory, '/arm_controller/joint_trajectory', 10)


def esperar(s):
    t0 = time.time()
    while time.time() - t0 < s: rclpy.spin_once(n, timeout_sec=0.05)


esperar(3)
peor = 0
for q in POSES:
    m = JointTrajectory(); m.joint_names = JOINTS; p = JointTrajectoryPoint(); p.positions = [float(x) for x in q]; p.time_from_start.sec = 3; m.points = [p]
    pub.publish(m); esperar(6)
    qm = [js.get(j, np.nan) for j in JOINTS]
    try:
        T = buf.lookup_transform('base_footprint', 'gripper_frame_link', rclpy.time.Time())
    except Exception as e:
        print('sin TF:', e); continue
    t = T.transform.translation; real = np.array([t.x, t.y, t.z])
    prop, _ = fk(np.array(qm))
    d = float(np.linalg.norm(real - prop)); peor = max(peor, d)
    print(f'q={np.round(q, 2)} | q medida={np.round(qm, 3)} | TF Gazebo={np.round(real, 4)} | FK propia={np.round(prop, 4)} | dif={d * 1000:.2f} mm')
print(f'PEOR DIFERENCIA: {peor * 1000:.2f} mm')
rclpy.shutdown()
