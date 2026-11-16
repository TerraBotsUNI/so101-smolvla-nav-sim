#!/usr/bin/python3
"""Percepción + control del SO-101 sobre el Waffle Pi (versión 2) (ROS 2 Humble / Gazebo Fortress).

Percepción: el robot NO conoce la posición del cubo. Segmenta el color verde en la imagen de la cámara de muñeca y proyecta el centroide
sobre el plano horizontal a la altura del centro del cubo, usando la TF (base_footprint <- wrist_camera_link) y el modelo de cámara pinhole.
La verdad de terreno de Gazebo (/gt_tf) se usa SOLO para medir (error de estimación y éxito), nunca para decidir.
"""
import math, os, sys, time, subprocess
import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.parameter import Parameter
from sensor_msgs.msg import Image, JointState
from tf2_msgs.msg import TFMessage
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import GripperCommand
from tf2_ros import Buffer, TransformListener

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from so101_kinematics import ik as _ik, fk as _fk, JOINTS as SO_JOINTS, GRIPPER_LIM

CAM_HFOV, CAM_W, CAM_H = 1.3, 640, 480        # debe coincidir con fortress_sim.xacro (wrist_camera)
CAM_OFFSET = (0.025, 0.0, 0.0)                # pose del sensor dentro de wrist_camera_link
CAMS = {   # cámara -> (atributo de imagen, marco TF, FOV horizontal, ancho, alto, desfase del sensor en su marco)
    'wrist': ('img', 'wrist_camera_link', 1.3, 640, 480, (0.025, 0.0, 0.0)),
    'front': ('img_front', 'camera_rgb_frame', 1.085595, 640, 480, (0.0, 0.0, 0.0)),
}
CUBE_SIZE = 0.04                              # debe coincidir con pick_object.size de config/arena.yaml
JOINTS = list(SO_JOINTS)                      # shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll
GRIP_OPEN, GRIP_CLOSE = 1.0, 0.0                   # PROVISIONAL: se calibra con so101_explorar.py (rango de la pinza -0.17 a 1.75 rad)
REC_JOINTS = JOINTS + ['gripper', 'wheel_left_joint', 'wheel_right_joint']


def quat_to_R(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


# color -> (canal dominante, nombre del modelo en Gazebo). El verde conserva el nombre histórico `pick_object`.
COLORES = {'rojo': (0, 'cubo_rojo'), 'verde': (1, 'pick_object'), 'azul': (2, 'cubo_azul')}
TARGET = {'color': 'verde'}                   # cubo pedido ahora (lo cambia el servidor del brazo en cada orden)


def target_name():
    return COLORES[TARGET['color']][1]


def detect_color(rgb, color='verde'):
    """Como detect_green pero para el canal del color pedido: (u, v, n, bbox) de la cara superior del cubo, o None."""
    k = COLORES[color][0]; ch = [rgb[..., i].astype(np.int16) for i in range(3)]
    c, o1, o2 = ch[k], ch[(k + 1) % 3], ch[(k + 2) % 3]
    m = (c > 70) & (c > 1.8 * o1) & (c > 1.8 * o2)
    if int(m.sum()) < 40:
        return None
    cmax = np.percentile(c[m], 95)
    top = m & (c >= 0.88 * cmax)
    if int(top.sum()) < 25:
        top = m
    # si hay varias manchas del mismo color nos quedamos con la mayor (componentes conexas)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(top.astype(np.uint8), 8)
    if n > 2:
        top = lab == (1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA])))
    vs, us = np.nonzero(top)
    cs, _ = cv2.findContours(top.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    pts = max(cs, key=cv2.contourArea).reshape(-1, 2).astype(float) if cs else None
    return float(us.mean()), float(vs.mean()), int(top.sum()), (int(us.min()), int(vs.min()), int(us.max()), int(vs.max())), pts


def detect_green(rgb):
    """rgb: array HxWx3 uint8. Devuelve (u, v, n_pixeles, bbox) de la CARA SUPERIOR del cubo verde, o None.
    El cubo visto en perspectiva muestra su cara superior (la más iluminada) y una lateral más oscura: usar todo el verde sesgaba la estimación
    ~12 mm hacia el robot, así que se toman solo los píxeles verdes más claros (cara superior)."""
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    m = (g > 70) & (g > 1.8 * r) & (g > 1.8 * b)
    n = int(m.sum())
    if n < 40:
        return None
    gmax = np.percentile(g[m], 95)
    top = m & (g >= 0.88 * gmax)
    if int(top.sum()) < 25:
        top = m
    vs, us = np.nonzero(top)
    return float(us.mean()), float(vs.mean()), int(top.sum()), (int(us.min()), int(vs.min()), int(us.max()), int(vs.max()))


class Manip(Node):
    def __init__(self, name='paper_vla_manip'):
        super().__init__(name, parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.img = None; self.img_front = None; self.js = {}; self.gt = {}
        self.rec = None
        self.create_subscription(Image, '/wrist_camera/image_raw', lambda m: self._img('img', 'wrist', m), 2)
        self.create_subscription(Image, '/camera/image_raw', lambda m: self._img('img_front', 'front', m), 2)
        self.img_scene = None                         # cámara de escena del mástil (entrada del VLA junto con la de muñeca)
        self.create_subscription(Image, '/scene_camera/image_raw', lambda m: setattr(self, 'img_scene', m), 2)
        self.vistas = {}; self.snap_dir = None; self.snap_cams = (); self.snap_n = 0
        for _v in ('vista_arena', 'vista_robot', 'vista_robot2', 'vista_meta'):
            self.create_subscription(Image, f'/{_v}/image_raw', (lambda m, v=_v: self.vistas.__setitem__(v, m)), 2)
        self.create_subscription(JointState, '/joint_states', self._js, 10)
        self.create_subscription(TFMessage, '/gt_tf', self._gt, 10)
        self.pub = self.create_publisher(JointTrajectory, '/arm_controller/joint_trajectory', 10)
        self.grip = ActionClient(self, GripperCommand, '/gripper_controller/gripper_cmd')
        self.tfbuf = Buffer(); self.tfl = TransformListener(self.tfbuf, self)

    # ---------------- utilidades de tiempo / suscripciones
    def _js(self, m):
        self.js = dict(zip(m.name, m.position))
        r = self.rec
        if r is not None:
            r['js'].append([self.now()] + [self.js.get(n, float('nan')) for n in REC_JOINTS])

    def _img(self, attr, cam, m):
        setattr(self, attr, m)
        r = self.rec
        if r is not None and cam in r['cams']:
            r['n'][cam] = r['n'].get(cam, 0) + 1
            if r['n'][cam] % 2 == 0:                         # una de cada dos imágenes, a 320x240, en MP4
                rgb = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3)
                w = r['vw'].get(cam)
                if w is None:
                    w = cv2.VideoWriter(f"{r['base']}_{cam}.mp4", cv2.VideoWriter_fourcc(*'mp4v'), 10, (320, 240)); r['vw'][cam] = w
                w.write(cv2.cvtColor(cv2.resize(rgb, (320, 240)), cv2.COLOR_RGB2BGR))
                r['ft'].append((self.now(), cam))

    # ---------------- grabación de cada ensayo (videos, articulaciones, verdad de terreno, eventos)
    def start_recording(self, base, cams=('wrist',)):
        os.makedirs(os.path.dirname(base) or '.', exist_ok=True)
        self.rec = {'base': base, 'cams': cams, 'vw': {}, 'n': {}, 'js': [], 'gt': [], 'ft': [], 'ev': []}

    def mark(self, label):
        if self.rec is not None:
            self.rec['ev'].append((self.now(), label))
        if self.snap_dir:
            self.snap(label)

    def snap(self, label):
        """Fotografía (PNG a resolución completa) de las cámaras externas `snap_cams` en este instante (figuras del paper)."""
        import re as _re
        self.snap_n += 1
        for v in self.snap_cams:
            m = self.vistas.get(v)
            if m is None:
                continue
            rgb = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3)
            nm = _re.sub(r'[^A-Za-z0-9_.-]+', '_', label)[:40]
            cv2.imwrite(f"{self.snap_dir}/{self.snap_n:02d}_{nm}_{v}.png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

    def stop_recording(self):
        r, self.rec = self.rec, None
        if r is None:
            return
        import csv
        for w in r['vw'].values():
            w.release()
        def dump(name, header, rows):
            with open(f"{r['base']}_{name}.csv", 'w', newline='') as f:
                wr = csv.writer(f); wr.writerow(header); wr.writerows(rows)
        dump('joints', ['t_sim'] + REC_JOINTS, r['js'])
        dump('gt', ['t_sim'] + [f'cubo_{k}' for k in 'x y z qx qy qz qw'.split()] + [f'robot_{k}' for k in 'x y z qx qy qz qw'.split()], r['gt'])
        dump('eventos', ['t_sim', 'evento'], r['ev'])
        dump('fotogramas', ['t_sim', 'camara'], r['ft'])

    def _gt(self, m):
        for t in m.transforms:
            tr, q = t.transform.translation, t.transform.rotation
            self.gt[t.child_frame_id] = (tr.x, tr.y, tr.z, q.x, q.y, q.z, q.w)
        r = self.rec
        if r is not None and target_name() in self.gt and 'tb3_so101' in self.gt:
            r['gt'].append([self.now()] + list(self.gt[target_name()]) + list(self.gt['tb3_so101']))

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def spin_for(self, sec):
        t0 = self.now()
        while self.now() - t0 < sec and rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.02)

    def wait_data(self, timeout=60.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.img is not None and len(self.js) >= 6 and self.now() > 1.0:
                return True
        return False

    # ---------------- verdad de terreno (SOLO para medir)
    def gt_cube_in_footprint(self):
        rb, c = self.gt.get('tb3_so101'), self.gt.get(target_name())
        if rb is None or c is None:
            return None
        R = quat_to_R(*rb[3:]); p = R.T @ (np.array(c[:3]) - np.array(rb[:3]))
        return p

    # ---------------- percepción
    def see_cube(self, cam='wrist'):
        """Estima el centro del cubo en base_footprint (x, y, z) con la cámara `cam` ('wrist' o 'front'), o None. Devuelve (estimación, info)."""
        attr, frame, hfov, W, H, off = CAMS[cam]
        setattr(self, attr, None)
        t0 = time.time()
        while getattr(self, attr) is None and time.time() - t0 < 20:
            rclpy.spin_once(self, timeout_sec=0.05)
        m = getattr(self, attr)
        if m is None:
            return None, {'motivo': 'sin imagen'}
        rgb = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3)
        det = detect_color(rgb, TARGET['color'])
        if det is None:
            return None, {'motivo': 'no se ve el cubo'}
        u, v, n, bbox = det[:4]
        pts = det[4] if len(det) > 4 else None
        try:
            T = self.tfbuf.lookup_transform('base_footprint', frame, rclpy.time.Time())
        except Exception as e:
            return None, {'motivo': f'sin TF: {e}'}
        tr, q = T.transform.translation, T.transform.rotation
        R = quat_to_R(q.x, q.y, q.z, q.w)
        origin = R @ np.array(off) + np.array([tr.x, tr.y, tr.z])
        fx = (W / 2) / math.tan(hfov / 2)
        d = R @ np.array([1.0, -(u - W / 2) / fx, -(v - H / 2) / fx])
        zc = CUBE_SIZE                  # el centroide detectado es el de la cara superior (a z = tamaño del cubo)
        if d[2] >= -1e-3:
            return None, {'motivo': 'rayo no baja'}
        t_ = (zc - origin[2]) / d[2]
        p = origin + t_ * d
        yaw = None                      # orientación del cubo: el contorno de la cara superior proyectado al plano z = CUBE_SIZE es un cuadrado
        if pts is not None and len(pts) >= 8:
            D = (R @ np.stack([np.ones(len(pts)), -(pts[:, 0] - W / 2) / fx, -(pts[:, 1] - H / 2) / fx])).T
            ok = D[:, 2] < -1e-3
            if ok.sum() >= 8:
                P = origin + ((zc - origin[2]) / D[ok, 2])[:, None] * D[ok]
                (_, _), (_, _), ang = cv2.minAreaRect((P[:, :2] * 1000).astype(np.float32))
                yaw = math.radians(((ang + 45) % 90) - 45)          # en base_footprint, en [-45, 45) grados (simetría del cubo)
        self.last_cube_yaw = yaw
        return p, {'pix': (u, v), 'n': n, 'bbox': bbox, 'yaw': yaw}

    def save_image(self, path):
        """Guarda el último fotograma de la cámara de muñeca como PPM (depuración)."""
        self.img = None; t0 = time.time()
        while self.img is None and time.time() - t0 < 10:
            rclpy.spin_once(self, timeout_sec=0.05)
        if self.img is not None:
            open(path, 'wb').write(f'P6 {self.img.width} {self.img.height} 255\n'.encode() + bytes(self.img.data))

    # ---------------- control del brazo
    def tcp_to_q(self, x_fp, y_fp, z_world, phi_deg, roll=0.0, q0=None, tol_inc=3.0):
        """Objetivo de la punta de la pinza en base_footprint (x, y) y altura sobre el suelo (z) con el eje de aproximación inclinado `phi_deg` hacia abajo
        -> las 5 articulaciones (IK numérica de so101_kinematics), o None si no llega con error < 3 mm y < 3 grados."""
        r = _ik(np.array([x_fp, y_fp, z_world]), phi_deg, q0=q0, roll=roll)       # q0: semilla (misma rama de la solución)
        if r is None or r[1] > 0.003 or r[2] > tol_inc:
            return None
        return r[0]

    def move_q(self, q, dur=2.5, tol=0.03):
        msg = JointTrajectory(); msg.joint_names = JOINTS
        p = JointTrajectoryPoint(); p.positions = [float(v) for v in q]
        p.time_from_start.sec = int(dur); p.time_from_start.nanosec = int((dur % 1) * 1e9)
        msg.points = [p]
        self.pub.publish(msg)
        self.spin_for(dur + 0.3)
        t0 = self.now()
        while self.now() - t0 < 3.0:
            rclpy.spin_once(self, timeout_sec=0.02)
            if all(abs(self.js.get(j, 9) - v) < tol for j, v in zip(JOINTS, q)):
                break
        return max(abs(self.js.get(j, 9) - v) for j, v in zip(JOINTS, q))

    def gripper(self, pos, effort=1.0, wait=2.0, tries=3):
        """Manda la pinza a `pos` y espera `wait` s de simulación. No se fía del resultado de la acción (el controlador puede darla por
        'atascada' antes de moverse); si la pinza no se mueve nada, reenvía la orden."""
        if not self.grip.wait_for_server(timeout_sec=10):
            return None
        dbg = os.environ.get('MANIP_DEBUG')
        p0 = self.js.get('gripper', 0.0)
        for k in range(tries):
            g = GripperCommand.Goal(); g.command.position = float(pos); g.command.max_effort = float(effort)
            fut = self.grip.send_goal_async(g)
            t0 = self.now()
            while not fut.done() and self.now() - t0 < 4.0:
                rclpy.spin_once(self, timeout_sec=0.02)
            gh = fut.result() if fut.done() else None
            self.spin_for(wait)
            p1 = self.js.get('gripper', 0.0)
            if dbg:
                print(f'  [dbg] pinza -> {pos:+.3f}: aceptada={None if gh is None else gh.accepted} {p0:+.4f} -> {p1:+.4f} (intento {k+1})', flush=True)
            if abs(p1 - p0) > 0.002 or abs(p1 - pos) < 0.004:
                break
        return self.js.get('gripper')


def set_cube_pose(x, y, yaw, z=CUBE_SIZE / 2 + 0.002, name=None):
    """Coloca el cubo en el mundo (preparar un ensayo; no es percepción)."""
    req = f'name: "{name or target_name()}" position {{x: {x:.4f} y: {y:.4f} z: {z:.4f}}} orientation {{x: 0 y: 0 z: {math.sin(yaw/2):.5f} w: {math.cos(yaw/2):.5f}}}'
    r = subprocess.run(['ign', 'service', '-s', '/world/paper_vla_world/set_pose', '--reqtype', 'ignition.msgs.Pose',
                        '--reptype', 'ignition.msgs.Boolean', '--timeout', '4000', '--req', req], capture_output=True, text=True, timeout=15)
    return 'true' in r.stdout

