#!/usr/bin/python3
"""Banco de evaluación del brazo: VLA contra experto clásico en las MISMAS escenas (diseño pareado).
Cada escena: 3 cubos barajados delante del robot como en las demostraciones (pedido a 14-18 cm, los otros a +-12.5-14.5 cm, giros de hasta 40 grados)
y un color pedido. Para cada estrategia se repone la escena idéntica y se pide la acción Pick. Una fila por (escena, estrategia) en el CSV.
Las poses de los cubos son RESPECTO AL ROBOT: el robot deriva ~1.5 cm y 4-5° por agarre, así que antes de cada intento se devuelve a su pose
inicial si se movió más de 2 cm o 2° y los cubos se colocan respecto a su pose real (verdad de terreno de Gazebo), igual que en las demostraciones.
Requiere cinematica.launch.py (sin Nav2) y, para «vla», el servidor de la política corriendo.
Uso: ros2 run paper_vla_tb3so101 so101_eval_brazo.py --n 10 --seed 900 --estrategias vla,ik_directa --out ~/eval_brazo.csv"""
import argparse, csv, math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.task import Future
from std_srvs.srv import Trigger
from tf2_msgs.msg import TFMessage
from paper_vla_interfaces.action import Pick
from so101_manipulation import set_cube_pose

COLORES = {'rojo': 'cubo_rojo', 'verde': 'pick_object', 'azul': 'cubo_azul'}
CAMPOS = ['escena', 'semilla', 'color', 'estrategia', 'exito', 'mensaje', 'cubo_z', 'duracion_s', 'ms_inferencia', 'cubos']


def escena(rng):
    color = rng.choice(list(COLORES)); otros = [c for c in COLORES if c != color]; rng.shuffle(otros)
    tx, ty = rng.uniform(0.14, 0.18), rng.uniform(-0.025, 0.025)
    poses = {color: (tx, ty, math.radians(rng.uniform(-40, 40)))}
    lados = [1, -1]; rng.shuffle(lados)
    for c, s in zip(otros, lados):
        poses[c] = (rng.uniform(0.13, 0.19), ty + s * rng.uniform(0.125, 0.145), math.radians(rng.uniform(-40, 40)))
    return color, poses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=10); ap.add_argument('--seed', type=int, default=900)
    ap.add_argument('--estrategias', default='vla,ik_directa'); ap.add_argument('--out', default='eval_brazo.csv')
    ap.add_argument('--desde', type=int, default=0, help='reanudar: salta las primeras k escenas (las genera igual para conservar la secuencia)')
    a = ap.parse_args()
    rclpy.init(); n = Node('so101_eval_brazo', parameter_overrides=[Parameter('use_sim_time', value=True)])
    cl = ActionClient(n, Pick, '/so101/pick'); obs = n.create_client(Trigger, '/so101/observe')
    gt = {}
    n.create_subscription(TFMessage, '/gt_tf', lambda m: gt.update({t.child_frame_id: t.transform for t in m.transforms}), 10)

    def pose_robot():
        rclpy.spin_until_future_complete(n, Future(), timeout_sec=0.3)
        t = gt['tb3_so101']; q = t.rotation
        return t.translation.x, t.translation.y, t.translation.z, math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))

    def colocar(poses):
        p = pose_robot()
        if math.hypot(p[0] - P0[0], p[1] - P0[1]) > 0.02 or abs(math.remainder(p[3] - P0[3], 2 * math.pi)) > math.radians(2):
            set_cube_pose(P0[0], P0[1], P0[3], z=P0[2] + 0.005, name='tb3_so101')
            rclpy.spin_until_future_complete(n, Future(), timeout_sec=1.5); p = pose_robot(); reub[0] += 1
        x0, y0, _, th = p; c, s_ = math.cos(th), math.sin(th)
        for col, (x, y, yaw) in poses.items():
            set_cube_pose(x0 + c * x - s_ * y, y0 + s_ * x + c * y, yaw + th, name=COLORES[col])
    if not cl.wait_for_server(timeout_sec=120):
        print('no está /so101/pick (¿cinematica.launch.py?)'); return 2
    for _ in range(100):
        if 'tb3_so101' in gt:
            break
        rclpy.spin_until_future_complete(n, Future(), timeout_sec=0.2)
    P0 = pose_robot(); reub = [0]
    rng = random.Random(a.seed); nuevo = not os.path.exists(a.out)
    with open(a.out, 'a', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        for i in range(a.n):
            color, poses = escena(rng)
            if i < a.desde:
                continue
            for est in a.estrategias.split(','):
                f = obs.call_async(Trigger.Request()); rclpy.spin_until_future_complete(n, f, timeout_sec=60)
                colocar(poses)
                t0 = n.get_clock().now()
                rclpy.spin_until_future_complete(n, Future(), timeout_sec=1.5)
                g = Pick.Goal(); g.strategy = est; g.color = color; g.hold = False
                fut = cl.send_goal_async(g); rclpy.spin_until_future_complete(n, fut); gh = fut.result()
                if not gh.accepted:
                    print(f'[{i}] {est}: objetivo rechazado'); continue
                rf = gh.get_result_async(); rclpy.spin_until_future_complete(n, rf); r = rf.result().result
                w.writerow(dict(escena=i, semilla=a.seed, color=color, estrategia=est, exito=int(r.success), mensaje=r.message, cubo_z=round(r.cube_z, 3),
                                duracion_s=round(r.duration_s, 1), ms_inferencia=round(r.est_error_mm, 1) if est == 'vla' else '',
                                cubos=';'.join(f'{c}:{x:.3f},{y:.3f},{math.degrees(yw):.0f}' for c, (x, y, yw) in poses.items()))); fh.flush()
                print(f'[{i}] pedido {color:5s} | {est:11s}: {"OK" if r.success else "FALLO"} {r.message} (cubo_z={r.cube_z:.3f})', flush=True)
    print(f'robot devuelto a su pose inicial {reub[0]} veces', flush=True)
    rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
