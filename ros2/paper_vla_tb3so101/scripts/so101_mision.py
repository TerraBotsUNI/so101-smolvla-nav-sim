#!/usr/bin/python3
"""Misión completa (máquina de estados) con el experto clásico: Nav2 -> recoger -> Nav2 -> colocar.
  INICIO -> IR_A_RECOJO (Nav2) -> ACERCAR (cámara + odometría) -> RECOGER (/so101/pick, hold) [hasta 2 intentos] -> IR_A_ENTREGA (Nav2) -> COLOCAR (/so101/place) -> [VOLVER a inicio] -> FIN
Las poses salen de config/ubicaciones.yaml (marco map). El cubo está a `delante` m del punto de recojo y el plato a `delante` m del punto de entrega.
Cada misión escribe una fila en el CSV (éxito y tiempo por etapa). La verdad de terreno de Gazebo (/gt_tf) SOLO se usa para medir y para reponer el escenario entre misiones.
Requiere: cinematica.launch.py nav:=true controller:=mision  (sim + Nav2 + servidor del brazo)
En la zona de recojo hay 3 cubos (rojo, verde, azul) barajados; --color elige cuál se pide.
Uso: ros2 run paper_vla_tb3so101 so101_mision.py --n 3 --out ~/misiones.csv"""
import argparse, csv, math, os, subprocess, sys, time
import rclpy, yaml
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_srvs.srv import Trigger
from nav2_msgs.srv import ClearEntireCostmap
from tf2_msgs.msg import TFMessage
from paper_vla_interfaces.action import Pick
from paper_vla_interfaces.srv import Locate
import random

DELANTE = 0.16          # m: distancia del cubo (y del plato) delante de base_footprint cuando el robot está en su punto
PLATO_R = 0.10          # m: radio del plato de entrega
COLORES = {'rojo': 'cubo_rojo', 'verde': 'pick_object', 'azul': 'cubo_azul'}
SEP = 0.13            # m: separación lateral entre los cubos de la zona de recojo
FIELDS = ['mision', 'color', 'orden_cubos', 'cubo_correcto', 'exito', 'etapa_fallo', 'nav1_ok', 'nav1_s', 'nav1_err_mm', 'acercar_ok', 'pick_ok', 'pick_intentos', 'pick_msg', 'pick_s', 'cubo_z_alzado',
          'nav2_ok', 'nav2_s', 'nav2_err_mm', 'cubo_sujeto', 'place_ok', 'place_msg', 'place_s', 'cubo_err_plato_mm', 'total_s', 'afinar_err_mm']


def set_model_pose(name, x, y, z, yaw):
    req = f'name: "{name}" position {{x: {x:.4f} y: {y:.4f} z: {z:.4f}}} orientation {{x: 0 y: 0 z: {math.sin(yaw/2):.5f} w: {math.cos(yaw/2):.5f}}}'
    r = subprocess.run(['ign', 'service', '-s', '/world/paper_vla_world/set_pose', '--reqtype', 'ignition.msgs.Pose', '--reptype', 'ignition.msgs.Boolean',
                        '--timeout', '4000', '--req', req], capture_output=True, text=True, timeout=15)
    return 'true' in r.stdout


def yaw_of(q):
    return math.atan2(2 * (q[3] * q[2] + q[0] * q[1]), 1 - 2 * (q[1] ** 2 + q[2] ** 2))


class Mision(Node):
    def __init__(self, ub, cube_size, seed=1):
        super().__init__('so101_mision', parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.ub, self.cs, self.gt = ub, cube_size, {}
        self.color, self.rng = 'verde', random.Random(seed)
        self.locate = self.create_client(Locate, '/so101/locate')
        self.create_subscription(TFMessage, '/gt_tf', self._gt, 20)
        self.nav = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.pick = ActionClient(self, Pick, '/so101/pick')
        self.srv = {k: self.create_client(Trigger, f'/so101/{k}') for k in ('observe', 'place', 'release', 'ver')}
        self.pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 1)
        self.clear = [self.create_client(ClearEntireCostmap, s) for s in ('/global_costmap/clear_entirely_global_costmap', '/local_costmap/clear_entirely_local_costmap')]
        self.vel = self.create_publisher(Twist, '/cmd_vel', 10)
        self.amcl = None
        from tf2_ros import Buffer, TransformListener
        self.tfbuf = Buffer(); self.tfl = TransformListener(self.tfbuf, self)
        from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', lambda m: setattr(self, 'amcl', m),
                                 QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.odom = None
        self.create_subscription(Odometry, '/odom', lambda m: setattr(self, 'odom', m), 10)

    def _gt(self, m):
        for t in m.transforms:
            tr, q = t.transform.translation, t.transform.rotation
            self.gt[t.child_frame_id] = (tr.x, tr.y, tr.z, q.x, q.y, q.z, q.w)

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def spin_for(self, s):
        t0 = self.now()
        while self.now() - t0 < s and rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.05)

    def wait_servers(self, timeout=180):
        """Espera a Nav2 y al servidor del brazo diciendo a qué espera (antes se quedaba callado)."""
        for nombre, listo in (('Nav2 (/navigate_to_pose)', lambda t: self.nav.wait_for_server(timeout_sec=t)),
                              ('brazo (/so101/pick)', lambda t: self.pick.wait_for_server(timeout_sec=t)),
                              ('brazo (/so101/locate)', lambda t: self.locate.wait_for_service(timeout_sec=t))):
            if listo(2.0):
                continue
            print(f'esperando a {nombre}...', flush=True)
            if not listo(timeout):
                print(f'NO responde {nombre} tras {timeout} s. Si es Nav2, mira en la terminal del launch si quedó en "Configuring" (relanza);'
                      ' si es el brazo, busca "so101_manip_server ... died".', flush=True)
                return False
        return all(c.wait_for_service(timeout_sec=10) for c in self.srv.values())

    def call(self, k, timeout=90):
        f = self.srv[k].call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, f, timeout_sec=timeout)
        r = f.result()
        return (r.success, r.message) if r is not None else (False, 'sin respuesta')

    def cube_world(self, color=None):
        g = self.gt.get(COLORES[color or self.color])
        return None if g is None else g[:3]

    def robot_xy(self):
        g = self.gt.get('tb3_so101')
        return None if g is None else g[:2]

    # ---------- ubicaciones
    def loc(self, name):
        x, y, yaw = self.ub[name]
        return x, y, yaw

    def ahead(self, name, d=DELANTE):
        x, y, yaw = self.loc(name)
        return x + d * math.cos(yaw), y + d * math.sin(yaw)

    # ---------- navegación
    def go_to(self, name, timeout=150, intentos=2):
        """Nav2 a la ubicación ; si falla, limpia los costmaps y reintenta (hasta ). Devuelve (ok, segundos, error real mm)."""
        t0 = self.now(); ok, err = False, None
        for k in range(intentos):
            ok, _, err = self._go_to(name, timeout)
            if ok:
                break
            print(f'    Nav2 falló (intento {k + 1}): limpio costmaps y reintento', flush=True)
            for c in self.clear:
                if c.wait_for_service(timeout_sec=5):
                    f = c.call_async(ClearEntireCostmap.Request()); rclpy.spin_until_future_complete(self, f, timeout_sec=5)
            self.spin_for(1.0)
        return ok, self.now() - t0, err

    def _go_to(self, name, timeout=150):
        x, y, yaw = self.loc(name)
        g = NavigateToPose.Goal(); g.pose = PoseStamped(); g.pose.header.frame_id = 'map'
        g.pose.pose.position.x, g.pose.pose.position.y = x, y
        g.pose.pose.orientation.z, g.pose.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        t0 = self.now()
        fut = self.nav.send_goal_async(g); rclpy.spin_until_future_complete(self, fut, timeout_sec=30)
        gh = fut.result()
        if gh is None or not gh.accepted:
            return False, self.now() - t0, None
        rf = gh.get_result_async()
        while not rf.done() and self.now() - t0 < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)
        if not rf.done():
            gh.cancel_goal_async(); self.spin_for(1.0)
            return False, self.now() - t0, self._err(x, y)
        ok = rf.result().status == GoalStatus.STATUS_SUCCEEDED
        self.spin_for(1.0)                                  # que el robot se asiente antes de mover el brazo
        return ok, self.now() - t0, self._err(x, y)

    # ---------- acercamiento fino (cámara de muñeca + odometría): deja el cubo a DELANTE m, centrado
    def _odom_pose(self):
        o = self.odom.pose.pose; q = o.orientation
        return o.position.x, o.position.y, math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2))

    def _drive(self, turn=0.0, dist=0.0, timeout=20.0):
        """Gira  rad y luego avanza  m con odometría (control proporcional, velocidades bajas)."""
        t0 = self.now(); x0, y0, a0 = self._odom_pose()
        while abs(turn) > 0.02 and self.now() - t0 < timeout:
            rclpy.spin_once(self, timeout_sec=0.05)
            d = math.atan2(math.sin(self._odom_pose()[2] - a0), math.cos(self._odom_pose()[2] - a0))
            e = turn - d
            if abs(e) < 0.01: break
            w = max(0.08, min(0.5, 1.5 * abs(e))) * (1 if e > 0 else -1)
            self.vel.publish(Twist(angular=type(Twist().angular)(z=w)))
        t1 = self.now()
        while dist != 0.0 and self.now() - t1 < timeout:
            rclpy.spin_once(self, timeout_sec=0.05)
            x, y, _ = self._odom_pose(); e = dist - math.copysign(math.hypot(x - x0, y - y0), dist)
            if abs(e) < 0.004 or e * dist < 0: break
            v = max(0.03, min(0.12, 1.2 * abs(e))) * (1 if dist > 0 else -1)
            self.vel.publish(Twist(linear=type(Twist().linear)(x=v)))
        self.vel.publish(Twist()); self.spin_for(0.8)

    def ver(self):
        rq = Locate.Request(); rq.color = self.color
        f = self.locate.call_async(rq); rclpy.spin_until_future_complete(self, f, timeout_sec=60)
        r = f.result()
        return (False, 'sin respuesta', 0.0, 0.0) if r is None else (r.success, r.message, r.x, r.y)

    def acercar(self):
        """Mira el cubo con la cámara de muñeca y corrige la pose de la base hasta que esté a DELANTE m de base_footprint y centrado. Devuelve (ok, mensaje)."""
        msg = ''
        ok, msg, x, y = self.ver()
        if not ok:                                   # BUSCAR: el cubo pedido puede quedar fuera del campo de la cámara (cubos a +-13 cm)
            for giro in (0.4, -0.8, 0.4):             # mira a un lado, al otro y vuelve
                self._drive(turn=giro); ok, msg, x, y = self.ver()
                print(f'    buscar: giro {math.degrees(giro):+.0f} grados -> {"visto" if ok else "no visto"}', flush=True)
                if ok:
                    break
            if not ok:
                return False, msg
        for it in range(3):
            if it > 0:
                ok, msg, x, y = self.ver()
                if not ok:
                    return False, msg
            if abs(x - DELANTE) < 0.015 and abs(y) < 0.02:
                return True, f'cubo a ({x:.3f}, {y:.3f})'
            ang = math.atan2(y, x)
            self._drive(turn=ang, dist=math.hypot(x, y) - DELANTE)
            print(f'    acercar {it + 1}: cubo visto en ({x:.3f}, {y:.3f}) -> giro {math.degrees(ang):.1f} grados, avanzo {1000 * (math.hypot(x, y) - DELANTE):.0f} mm', flush=True)
        ok, msg, _, _ = self.ver()
        return ok, msg

    def afinar(self, name, tol=0.015, iters=3):
        """Acercamiento fino tras Nav2 (como un «docking»): con la pose ESTIMADA por AMCL (TF map->base_footprint) gira hacia la meta,
        avanza (o retrocede si la meta queda detrás) con odometría y termina orientado al rumbo de la meta. Nav2 da la meta por
        alcanzada a < xy_goal_tolerance (0.12 m), y en la entrega no hay otra corrección antes de colocar. Devuelve el resto estimado (m)."""
        x, y, yaw = self.loc(name)
        ang_n = lambda a: math.atan2(math.sin(a), math.cos(a))
        d = None
        for it in range(iters):
            self.spin_for(0.5); p = self.pose_actual()
            if p is None:
                return None
            q = p.pose.pose.orientation; th = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2))
            dx, dy = x - p.pose.pose.position.x, y - p.pose.pose.position.y; d = math.hypot(dx, dy)
            if d < tol:
                break
            giro, dist = ang_n(math.atan2(dy, dx) - th), d
            if abs(giro) > math.pi / 2:                     # la meta queda detrás: retrocede en vez de dar media vuelta
                giro, dist = ang_n(giro - math.pi), -d
            print(f'    afinar {it + 1}: faltan {1000 * d:.0f} mm según AMCL -> giro {math.degrees(giro):+.1f} grados, avanzo {1000 * dist:+.0f} mm', flush=True)
            self._drive(turn=giro, dist=dist)
        self.spin_for(0.5); p = self.pose_actual()
        if p is not None:
            q = p.pose.pose.orientation; th = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2))
            e = ang_n(yaw - th)
            if abs(e) > 0.02:
                print(f'    afinar: oriento {math.degrees(e):+.1f} grados', flush=True); self._drive(turn=e)
        return d

    def _err(self, x, y):
        r = self.robot_xy()
        return None if r is None else 1000 * math.hypot(r[0] - x, r[1] - y)

    # ---------- escenario (preparación y medición; no es percepción del robot)
    def pose_actual(self):
        """Pose estimada AHORA (TF map -> base_footprint). No usar el último /amcl_pose: AMCL solo lo publica al moverse más de 5 cm o 0.05 rad
        y tras el acercamiento puede ser de mitad de un giro (fijarlo hacía que AMCL se perdiera)."""
        try:
            t = self.tfbuf.lookup_transform('map', 'base_footprint', rclpy.time.Time())
        except Exception:
            return None
        p = PoseWithCovarianceStamped(); p.header.frame_id = 'map'
        p.pose.pose.position.x, p.pose.pose.position.y = t.transform.translation.x, t.transform.translation.y
        p.pose.pose.orientation = t.transform.rotation
        return p

    def relocalizar(self, pose):
        """Vuelve a fijar en AMCL la pose que tenía antes de manipular: la base no se mueve mientras el brazo trabaja, y durante
        el agarre AMCL podía saltar a otra zona del mapa (Nav2 luego planificaba desde una pose falsa)."""
        if pose is None:
            return
        p = PoseWithCovarianceStamped(); p.header.frame_id = 'map'; p.pose.pose = pose.pose.pose
        p.pose.covariance[0] = p.pose.covariance[7] = 0.01; p.pose.covariance[35] = 0.005
        for _ in range(2):
            p.header.stamp = self.get_clock().now().to_msg(); self.pose_pub.publish(p); self.spin_for(0.3)
        self.spin_for(1.0)

    def reponer(self):
        """Pone al robot en `inicio`, el cubo en el punto de recojo y le dice a AMCL dónde está."""
        self.call('observe')
        x, y, yaw = self.loc('inicio')
        set_model_pose('tb3_so101', x, y, 0.02, yaw)
        cx, cy = self.ahead('recojo'); _, _, ryaw = self.loc('recojo')
        orden = list(COLORES); self.rng.shuffle(orden); self.orden = orden
        for k, col in enumerate(orden):                 # izquierda, centro, derecha (vistos desde el robot)
            d = (1 - k) * SEP
            set_model_pose(COLORES[col], cx - d * math.sin(ryaw), cy + d * math.cos(ryaw), self.cs / 2 + 0.002, ryaw)
        p = PoseWithCovarianceStamped(); p.header.frame_id = 'map'
        p.pose.pose.position.x, p.pose.pose.position.y = x, y
        p.pose.pose.orientation.z, p.pose.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        p.pose.covariance[0] = p.pose.covariance[7] = 0.05; p.pose.covariance[35] = 0.03
        for _ in range(3):
            p.header.stamp = self.get_clock().now().to_msg(); self.pose_pub.publish(p); self.spin_for(0.5)
        self.spin_for(3.0)

    # ---------- una misión
    def mision(self, i, volver):
        row = {k: '' for k in FIELDS}; row.update(mision=i, color=self.color, orden_cubos='-'.join(getattr(self, 'orden', []))); t_all = self.now()
        print(f'[{i}] PEDIDO: "quiero el cubo {self.color}"  (orden en la mesa: {row["orden_cubos"]})', flush=True)

        def fin(stage):
            row.update(exito=int(stage is None), etapa_fallo=stage or '', total_s=round(self.now() - t_all, 1)); return row

        print(f'[{i}] IR_A_RECOJO', flush=True)
        ok, s, err = self.go_to('recojo')
        row.update(nav1_ok=int(ok), nav1_s=round(s, 1), nav1_err_mm=None if err is None else round(err, 1))
        if not ok:
            return fin('nav_recojo')
        print(f'[{i}] ACERCAR', flush=True)
        okc, msgc = self.acercar()
        row['acercar_ok'] = int(okc); print('    ', msgc, flush=True)
        print(f'[{i}] RECOGER', flush=True)
        self.spin_for(1.0); pose_base = self.pose_actual()  # pose de la base antes de manipular (no se moverá)
        t0 = self.now(); r = None
        for k in (1, 2):                                   # hasta 2 intentos
            g = Pick.Goal(); g.strategy = ''; g.hold = True; g.color = self.color
            fut = self.pick.send_goal_async(g, feedback_callback=lambda fb: print('    etapa:', fb.feedback.stage, flush=True))
            rclpy.spin_until_future_complete(self, fut)
            gh = fut.result()
            rf = gh.get_result_async(); rclpy.spin_until_future_complete(self, rf); r = rf.result().result
            row['pick_intentos'] = k
            if r.success:
                break
            print(f'    intento {k} falló: {r.message}', flush=True)
        row.update(pick_ok=int(r.success), pick_msg=r.message, pick_s=round(self.now() - t0, 1), cubo_z_alzado=round(r.cube_z, 3))
        if not r.success:
            self.call('release'); self.call('observe')
            return fin('recoger')
        self.relocalizar(pose_base)
        print(f'[{i}] IR_A_ENTREGA', flush=True)
        ok, s, err = self.go_to('entrega')
        c = self.cube_world()
        row.update(nav2_ok=int(ok), nav2_s=round(s, 1), nav2_err_mm=None if err is None else round(err, 1),
                   cubo_sujeto=int(c is not None and c[2] > 0.05))
        if not ok:
            return fin('nav_entrega')
        if self.afinar_on:
            print(f'[{i}] AFINAR (pose AMCL)', flush=True); self.afinar('entrega')
            x_e, y_e, _ = self.loc('entrega'); e2 = self._err(x_e, y_e)
            row['afinar_err_mm'] = None if e2 is None else round(e2, 1)   # error real tras afinar (solo medición)
        print(f'[{i}] COLOCAR', flush=True)
        t0 = self.now(); ok, msg = self.call('place', 120)
        px, py = self.ahead('entrega'); c = self.cube_world()
        err_plato = None if c is None else 1000 * math.hypot(c[0] - px, c[1] - py)
        en_plato = c is not None and err_plato < 1000 * PLATO_R and c[2] < 0.05
        row.update(place_ok=int(ok and en_plato), place_msg=msg, place_s=round(self.now() - t0, 1),
                   cubo_err_plato_mm=None if err_plato is None else round(err_plato, 1))
        otros = [c for c in COLORES if c != self.color and self.cube_world(c) is not None and math.hypot(self.cube_world(c)[0] - px, self.cube_world(c)[1] - py) < PLATO_R]
        row['cubo_correcto'] = int(en_plato and not otros)
        if not (ok and en_plato):
            return fin('colocar')
        if volver:
            print(f'[{i}] VOLVER', flush=True); self.go_to('inicio')
        return fin(None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=1); ap.add_argument('--out', default='misiones_so101.csv')
    ap.add_argument('--ubicaciones', default=None, help='YAML de poses (por defecto config/ubicaciones.yaml del paquete)')
    ap.add_argument('--no-reponer', action='store_true', help='no recolocar robot ni cubo antes de la primera misión')
    ap.add_argument('--volver', action='store_true', help='al terminar, vuelve a inicio')
    ap.add_argument('--color', default='azar', help='rojo | verde | azul | azar (uno al azar por misión)')
    ap.add_argument('--seed', type=int, default=1, help='semilla del orden de los cubos y del color al azar')
    ap.add_argument('--sin-afinar', action='store_true', help='no hacer el acercamiento fino con AMCL en la entrega (comportamiento anterior)')
    ap.add_argument('--desde', type=int, default=0, help='reanudar: salta las primeras k misiones (consume su azar para conservar la secuencia)')
    a = ap.parse_args()
    pkg = get_package_share_directory('paper_vla_tb3so101')
    ub = yaml.safe_load(open(a.ubicaciones or os.path.join(pkg, 'config', 'ubicaciones.yaml'), encoding='utf-8'))
    rclpy.init(); n = Mision(ub, 0.04, a.seed)
    n.afinar_on = not a.sin_afinar
    if not n.wait_servers():
        print('faltan servidores: lanza antes  ros2 launch paper_vla_tb3so101 cinematica.launch.py nav:=true controller:=mision'); return 2
    n.spin_for(2.0)
    new = not os.path.exists(a.out); ok_total = 0
    with open(a.out, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i in range(a.n):
            n.color = n.rng.choice(list(COLORES)) if a.color == 'azar' else a.color
            if i < a.desde:                    # misma secuencia de colores y órdenes que sin el corte
                n.rng.shuffle(list(COLORES)); continue
            if i > 0 or not a.no_reponer:
                n.reponer()
            row = n.mision(i, a.volver); ok_total += row['exito']
            w.writerow(row); f.flush()
            print(f'[{i}] {"ÉXITO" if row["exito"] else "FALLO en " + row["etapa_fallo"]}  ({row["total_s"]} s de simulación)', flush=True)
    print(f'{ok_total}/{a.n} misiones completas -> {a.out}')
    rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
