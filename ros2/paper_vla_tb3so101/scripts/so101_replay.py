#!/usr/bin/python3
"""Diagnóstico: reproduce en lazo abierto las «acciones» de una demostración exitosa (estado medido del paso siguiente, lo mismo que aprende el VLA)
por el MISMO canal que el puente VLA (10 Hz, JointTrajectory de 0.12 s por punto, pinza por GripperCommand si cambia > 0.05), en la misma escena.
Si ni la reproducción perfecta levanta el cubo, el problema es la representación de la acción / el canal, no el modelo.
Uso: python3 so101_replay.py <ep_dir> [desfase_pasos]   (desfase k: usa el estado t+k como acción; k=1 es lo que aprende el VLA)"""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, rclpy
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import GripperCommand
import so101_manipulation as SM
import so101_trial as T
from so101_manipulation import Manip, set_cube_pose

ep = sys.argv[1]; k = int(sys.argv[2]) if len(sys.argv) > 2 else 1
BIN = len(sys.argv) > 3 and sys.argv[3] == 'bin'   # pinza binaria: si la acción pide cerrar (< 0.65) se manda GRIP_CLOSE con fuerza
meta = json.load(open(os.path.join(ep, 'meta.json'))); E = np.loadtxt(os.path.join(ep, 'estado.csv'), delimiter=',', skiprows=1)
rclpy.init(); m = Manip('so101_replay'); assert m.wait_data()
q_obs = m.tcp_to_q(T.OBS_XY[0], T.OBS_XY[1], T.Z_OBS, T.PHI_OBS)
m.gripper(T.GRIP_OPEN); m.move_q(q_obs, 3.0); m.spin_for(0.5)
x0, y0, z0, qx, qy, qz, qw = m.gt['tb3_so101']; th = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
c, s = math.cos(th), math.sin(th)
for col, (x, y, yaw) in meta['cubos'].items():
    set_cube_pose(x0 + c * x - s * y, y0 + s * x + c * y, yaw + th, name=SM.COLORES[col][1])
m.spin_for(1.5); SM.TARGET['color'] = meta['color']
t_next = m.now(); g_ult = None
for t in range(len(E) - k):
    while m.now() < t_next:
        rclpy.spin_once(m, timeout_sec=0.005)
    t_next += 0.1
    a = E[t + k, 1:7]
    tr = JointTrajectory(); tr.joint_names = list(SM.JOINTS)
    pt = JointTrajectoryPoint(); pt.positions = [float(v) for v in a[:5]]; pt.time_from_start.nanosec = int(1.2e8)
    tr.points = [pt]; m.pub.publish(tr)
    if g_ult is None or abs(a[5] - g_ult) > 0.05:
        g = GripperCommand.Goal(); g.command.position = float(SM.GRIP_CLOSE if (BIN and a[5] < 0.65) else a[5]); g.command.max_effort = 3.0
        m.grip.send_goal_async(g); g_ult = a[5]
m.spin_for(1.0)
gt = m.gt_cube_in_footprint()
print(f'reproducción k={k} bin={BIN} de {os.path.basename(ep)} ({meta["instruccion"]}): cubo z = {gt[2]:.3f} -> {"LEVANTADO" if gt[2] > 0.08 else "NO levantado"}', flush=True)
rclpy.shutdown()
