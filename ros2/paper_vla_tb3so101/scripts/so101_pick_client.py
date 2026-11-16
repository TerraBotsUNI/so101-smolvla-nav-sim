#!/usr/bin/python3
"""Cliente de prueba de /so101/pick: coloca el cubo al azar delante del robot (preparación del ensayo), pide recoger y guarda una fila por ensayo.
Uso: ros2 run paper_vla_tb3so101 so101_pick_client.py --strategy ik_directa --n 3 --seed 11 --out ~/pick.csv
     (--no-place: no mueve el cubo, recoge el que haya)"""
import argparse, csv, math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_srvs.srv import Trigger
from paper_vla_interfaces.action import Pick
from so101_manipulation import set_cube_pose


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strategy', default='ik_directa'); ap.add_argument('--n', type=int, default=3); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--fwd-min', type=float, default=0.13); ap.add_argument('--fwd-max', type=float, default=0.19); ap.add_argument('--lat', type=float, default=0.06)
    ap.add_argument('--yaw-deg', type=float, default=10.0); ap.add_argument('--hold', action='store_true'); ap.add_argument('--no-place', action='store_true')
    ap.add_argument('--out', default='pick_resultados.csv'); ap.add_argument('--color', default='verde')
    a = ap.parse_args()
    rclpy.init()
    n = Node('so101_pick_client', parameter_overrides=[Parameter('use_sim_time', value=True)])
    cl = ActionClient(n, Pick, '/so101/pick')
    obs = n.create_client(Trigger, '/so101/observe')
    if not cl.wait_for_server(timeout_sec=60):
        print('no está /so101/pick: ¿corre manipulation.launch.py?')
        return 2
    rng = random.Random(a.seed)
    rows = []
    for i in range(a.n):
        x, y = rng.uniform(a.fwd_min, a.fwd_max), rng.uniform(-a.lat, a.lat)
        yaw = math.radians(rng.uniform(-a.yaw_deg, a.yaw_deg))
        f = obs.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(n, f, timeout_sec=60)
        if not a.no_place:
            set_cube_pose(x, y, yaw, name={'rojo': 'cubo_rojo', 'verde': 'pick_object', 'azul': 'cubo_azul'}[a.color])
        g = Pick.Goal(); g.strategy = a.strategy; g.hold = a.hold; g.color = a.color
        fut = cl.send_goal_async(g, feedback_callback=lambda fb: print('   etapa:', fb.feedback.stage, flush=True))
        rclpy.spin_until_future_complete(n, fut)
        gh = fut.result()
        if not gh.accepted:
            print('objetivo rechazado (estrategia inválida)')
            return 1
        rf = gh.get_result_async()
        rclpy.spin_until_future_complete(n, rf)
        r = rf.result().result
        print(f'[{i}] {a.strategy}: {"OK" if r.success else "FALLO"} {r.message} cubo_z={r.cube_z:.3f} err_est={r.est_error_mm:.1f} mm', flush=True)
        rows.append(dict(ensayo=i, estrategia=a.strategy, cubo_x=round(x, 4), cubo_y=round(y, 4), exito=int(r.success), mensaje=r.message,
                         cubo_z=round(r.cube_z, 3), err_est_mm=round(r.est_error_mm, 1), tiempo_sim_s=round(r.duration_s, 1)))
    new = not os.path.exists(a.out)
    with open(a.out, 'a', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        if new:
            w.writeheader()
        w.writerows(rows)
    print(f'{sum(r["exito"] for r in rows)}/{len(rows)} éxitos -> {a.out}')
    rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
