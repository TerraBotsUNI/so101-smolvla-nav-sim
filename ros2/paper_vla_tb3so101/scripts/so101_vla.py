#!/usr/bin/python3
"""Puente ROS -> política VLA (estrategia «vla» de la acción Pick). La política corre en otro proceso (vla/servidor_politica.py, Python 3.12, GPU);
aquí, a 10 Hz de tiempo de simulación, se le envían las dos cámaras (256x256, como en las demostraciones), las 6 articulaciones y la instrucción,
y la acción recibida (posiciones objetivo de las 5 articulaciones y de la pinza) se aplica al brazo. Al terminar se mide el éxito igual que con el experto."""
import json, math, os, socket, struct, time
import cv2, numpy as np, rclpy
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import GripperCommand
import so101_manipulation as SM
import so101_trial as T

INGLES = {'rojo': 'red', 'verde': 'green', 'azul': 'blue'}
JOINTS6 = list(SM.JOINTS) + ['gripper']
# Pinza binaria (12-nov): las demostraciones guardan la posición MEDIDA de la pinza (~0.43 rad al tocar el cubo), no la orden del experto
# (cerrar del todo, GRIP_CLOSE, con fuerza: el cubo es lo que la detiene). Mandar la posición aprendida deja la pinza justo en contacto, sin
# fuerza, y el cubo resbala: ni la reproducción perfecta de una demostración lo levantaba (0/6); con la pinza binaria, 6/6.
UMBRAL_PINZA = 0.65      # rad: por debajo, la política está pidiendo cerrar (abierta = 0.85)


class ClienteVLA:
    def __init__(self, host='127.0.0.1', puerto=5555, timeout=30.0):
        self.s = socket.create_connection((host, puerto), timeout=timeout); self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def _rec(self, n):
        b = bytearray()
        while len(b) < n:
            p = self.s.recv(n - len(b))
            if not p:
                raise ConnectionError('servidor desconectado')
            b.extend(p)
        return bytes(b)

    def _pedir(self, h, datos=b''):
        c = json.dumps(h).encode(); self.s.sendall(struct.pack('>I', len(c)) + c + datos)
        (n,) = struct.unpack('>I', self._rec(4)); return json.loads(self._rec(n))

    def reset(self):
        return self._pedir({'tipo': 'reset'})

    def accion(self, tarea, estado, wrist, front):
        r = self._pedir({'tipo': 'accion', 'tarea': tarea, 'estado': [float(v) for v in estado], 'camaras': ['wrist', 'scene']}, wrist.tobytes() + front.tobytes())
        return np.array(r['accion'], float), r.get('ms', 0.0)


def _img256(msg):
    rgb = np.frombuffer(bytes(msg.data), np.uint8).reshape(msg.height, msg.width, 3)
    return np.ascontiguousarray(cv2.resize(rgb, (256, 256), interpolation=cv2.INTER_AREA))


def vla_cycle(m, color, row, q_obs, hold, cliente, t_max=35.0, hz=10.0, instruccion=None, grabar_dir=''):
    """Episodio con la política VLA: desde la pose de observación con la pinza abierta (igual que las demostraciones) durante t_max s de simulación."""
    tarea = instruccion or f'pick up the {INGLES[color]} cube'
    t_sim0, t_wall0 = m.now(), time.time()
    m.gripper(T.GRIP_OPEN); m.move_q(q_obs, 3.0); m.spin_for(0.5)
    cliente.reset(); m.mark(f'VLA: «{tarea}»')
    grab = None; acc_rows = []
    if grabar_dir:                                   # mismo grabador que las demostraciones (cámaras + estado a 10 Hz) y además las acciones pedidas
        import so101_demos
        d = os.path.join(os.path.expanduser(grabar_dir), time.strftime('vla_%H%M%S_') + color)
        if getattr(m, 'grab_vla', None) is None:      # un único grabador persistente por servidor del brazo (lanzar uno por intento fallaba a veces)
            m.grab_vla = so101_demos.Grabador(m, int(hz))
        grab = m.grab_vla
        if not grab.start(d):
            grab = None
    t_next = m.now(); g_ult = None; pasos = 0; ms = []
    while m.now() - t_sim0 < t_max and rclpy.ok():
        rclpy.spin_once(m, timeout_sec=0.005)
        if m.now() < t_next or m.img is None or m.img_scene is None or len(m.js) < 6:
            continue
        t_next += 1.0 / hz
        est = [m.js.get(j, 0.0) for j in JOINTS6]
        a, t_inf = cliente.accion(tarea, est, _img256(m.img), _img256(m.img_scene)); ms.append(t_inf); pasos += 1
        acc_rows.append([round(m.now(), 3)] + [round(float(v), 5) for v in est] + [round(float(v), 5) for v in a] + [t_inf])
        tr = JointTrajectory(); tr.joint_names = list(SM.JOINTS)
        pt = JointTrajectoryPoint(); pt.positions = [float(v) for v in a[:5]]; pt.time_from_start.nanosec = int(1.2e8)
        tr.points = [pt]; m.pub.publish(tr)
        g_cmd = SM.GRIP_CLOSE if a[5] < UMBRAL_PINZA else T.GRIP_OPEN
        if g_ult is None or g_cmd != g_ult:                     # la pinza solo se reordena si cambia de abrir a cerrar o al revés
            g = GripperCommand.Goal(); g.command.position = float(g_cmd); g.command.max_effort = 3.0
            m.grip.send_goal_async(g); g_ult = g_cmd
    m.spin_for(1.0)
    gt = m.gt_cube_in_footprint(); tcp = T.tcp_now(m)
    if grab is not None:
        grab.stop()
        with open(os.path.join(grab.d, 'acciones.csv'), 'w') as fa:
            fa.write('t_sim,' + ','.join('est_' + j for j in JOINTS6) + ',' + ','.join('acc_' + j for j in JOINTS6) + ',ms\n')
            for r_ in acc_rows:
                fa.write(','.join(str(v) for v in r_) + '\n')
        json.dump(dict(instruccion=tarea, color=color, exito=bool(gt is not None and gt[2] > 0.08), z_cubo=None if gt is None else float(gt[2]), pasos=pasos),
                  open(os.path.join(grab.d, 'meta.json'), 'w'), indent=1, ensure_ascii=False)
    ok = gt is not None and gt[2] > 0.08 and math.hypot(gt[0] - tcp[0], gt[1] - tcp[1]) < 0.07
    row.update(exito=int(ok), z_cubo_final='' if gt is None else round(float(gt[2]), 3), estrategia='vla', motivo='' if ok else 'no levantó el cubo',
               tiempo_sim_s=round(m.now() - t_sim0, 1), tiempo_real_s=round(time.time() - t_wall0, 1),
               detecciones=pasos, err_est1_mm='' if not ms else round(float(np.mean(ms)), 1))   # aquí: pasos de control y ms medios de inferencia
    if not (hold and ok):
        m.gripper(T.GRIP_OPEN); m.move_q(q_obs, 2.5)
    return row
