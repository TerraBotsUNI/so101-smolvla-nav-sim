#!/usr/bin/python3
"""Banco de pruebas de manipulación: repite N agarres del cubo verde con cada estrategia y guarda una fila por ensayo en un CSV.
El robot parte en el origen (0,0,0) con el brazo en la pose de observación; el cubo se coloca al azar delante (preparación del ensayo, NO se le dice al robot).
Estrategias (controladores clásicos, el robot solo usa la cámara de muñeca + su propia cinemática):
  ik_directa : 1 detección desde la pose de observación y 1 movimiento directo al agarre (lazo abierto).
  multietapa : va a un pre-agarre sobre la estimación, vuelve a detectar desde más cerca, corrige y baja.
  servovisual: pre-agarre y luego descenso en escalones; en cada escalón re-detecta y corrige con realimentación (ganancia 0.8) respecto al TCP medido (FK de joint_states).
Uso: ros2 run paper_vla_tb3so101 manip_trial.py --strategy all --n 10 --seed 1 --out resultados.csv
"""
import argparse, csv, math, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import rclpy
from so101_manipulation import Manip, set_cube_pose, GRIP_CLOSE, JOINTS, CUBE_SIZE
from so101_kinematics import fk, jaw_gap_vector

# Geometría de agarre del SO-101 (barrido del 11-nov-2026): las almohadillas de las mordazas se enfrentan a ~2 cm DETRÁS de la punta (TCP) y la mordaza móvil abre en horizontal
# (muñeca girada +-90 grados). El objetivo de la punta es  centro_cubo + D_PROF * eje_herramienta - MARGEN * u  (u = de la mordaza fija a la móvil).
PHI = 80.0                                   # inclinación de la pinza hacia abajo al agarrar (grados)
PHI_OBS = 40.0                               # inclinación en la pose de observación (muñeca sin girar)
ROLL = 1.5708                                # giro de muñeca al agarrar (rad) con el cubo alineado al robot
ROLL_ACT = ROLL                              # giro usado en este agarre: ROLL + corrección por la orientación del cubo vista por la cámara
TOL_CHOQUE = 0.15                            # rad: si al bajar alguna articulación queda más lejos que esto, la pinza chocó (con el cubo u otro): se aborta
MARGEN, D_PROF = 0.018, 0.016                # m (barrido del 11-nov: 5/5 con 0.018 / 0.016)
TOL_INC = 10.0                               # tolerancia de la inclinación de la pinza (grados): lo que importa es la posición; en el borde del alcance la inclinación no llega exacta
Q_REF = (0.0, 1.10, -0.41, 0.70)             # configuración de agarre que funcionó: semilla de la IK (evita ramas distintas del brazo)
GRIP_OPEN = 0.85                             # apertura al acercarse (rad)
DZ_HOVER, DZ_GRASP, Z_LIFT = 0.09, 0.0, 0.17   # altura del centro de las almohadillas sobre el centro del cubo (m); altura de levantado
Z_OBS = 0.20
CARRY_POSES = ()   # vacío: transporta en la pose de levantado (cubo a 16 cm delante, bajo el plano del LiDAR). Las poses cerca del cuerpo trababan el robot; el cabeceo se resolvió con la rueda loca delantera
OBS_XY = (0.10, 0.0)
STRATS = ['ik_directa', 'multietapa', 'servovisual']
FIELDS = ['muneca_deg', 'cubo_yaw_est_deg', 'cubo_yaw_real_deg', 'estrategia', 'ensayo', 'semilla', 'cubo_x', 'cubo_y', 'cubo_yaw_deg', 'est1_x', 'est1_y', 'err_est1_mm', 'err_est_final_mm',
          'err_tcp_mm', 'detecciones', 'exito', 'z_cubo_final', 'dist_cubo_tcp_mm', 'motivo', 'tiempo_sim_s', 'tiempo_real_s', 'carga_cpu', 'phi_agarre']


def lift_q(m, tcp):
    """Postura de levantado: sube la punta en vertical hasta Z_LIFT (o menos si no hay solución), con la misma inclinación y el mismo giro de muñeca."""
    for z in (Z_LIFT, 0.14, 0.11):
        for phi in (PHI, 70.0, 60.0):
            q = m.tcp_to_q(float(tcp[0]), float(tcp[1]), z, phi, ROLL_ACT, q0=np.array([m.js.get(j, 0.0) for j in JOINTS]))
            if q is not None:
                return q
    return None


def q_agarre(m, centro, phi=None):
    """Articulaciones para que las almohadillas rodeen un cubo cuyo centro está en `centro` (base_footprint): iteración sobre el eje de la herramienta y la dirección de cierre."""
    phi = PHI if phi is None else phi
    az = np.arctan2(centro[1], centro[0] + 0.111)
    a = np.array([np.cos(np.radians(phi)) * np.cos(az), np.cos(np.radians(phi)) * np.sin(az), -np.sin(np.radians(phi))])
    u = np.array([-np.sin(az), np.cos(az), 0.0]) * (1 if ROLL_ACT > 0 else -1)
    q = None
    for _ in range(4):
        tcp = centro + D_PROF * a - MARGEN * u
        tcp[2] = max(tcp[2], 0.004)
        q = m.tcp_to_q(float(tcp[0]), float(tcp[1]), float(tcp[2]), phi, ROLL_ACT, q0=np.array([*Q_REF, ROLL_ACT]), tol_inc=TOL_INC)
        if q is None:
            return None
        _, a = fk(q); gv = jaw_gap_vector(q, GRIP_OPEN); u = gv / np.linalg.norm(gv)
    return q


def roll_alineado(m, centro, phi, cube_yaw):
    """Giro de muñeca para que las mordazas cierren sobre dos caras paralelas del cubo (orientación cube_yaw en base_footprint).
    Prueba correcciones de -45 a +45 grados sobre ROLL y elige la que deja la dirección de cierre (horizontal) paralela a un eje del cubo."""
    global ROLL_ACT
    ROLL_ACT = ROLL
    if cube_yaw is None:
        return ROLL
    q = q_agarre(m, centro, phi)
    if q is None:
        return ROLL
    mejor, err_min = ROLL, 9.0
    for d in np.radians(np.arange(-45, 46, 3)):
        q2 = np.array(q, dtype=float); q2[4] = ROLL + d
        u = jaw_gap_vector(q2, GRIP_OPEN)
        e = ((math.atan2(u[1], u[0]) - cube_yaw + math.pi / 4) % (math.pi / 2)) - math.pi / 4
        if abs(e) < err_min:
            mejor, err_min = ROLL + d, abs(e)
    ROLL_ACT = mejor
    return mejor


def carry_q(m, tcp):
    """Postura de transporte: el cubo sujeto va por encima del plano del LiDAR (z=0.19 m; si no, Nav2 lo ve como obstáculo) y con el brazo recogido cerca de la
    pose de observación (con el brazo adelantado, como al agarrar, el centro de masa pasa por delante de las ruedas y el chasis cabecea 8 grados y se atasca)."""
    q0 = np.array([*Q_REF, ROLL_ACT])
    poses = [tuple(float(v) for v in p.split(',')) for p in os.environ['CARRY_ENV'].split(';')] if os.environ.get('CARRY_ENV') else CARRY_POSES   # CARRY_ENV='x,z,phi;...' solo para experimentos
    for x, z, phi in poses:
        q = m.tcp_to_q(x, 0.0, z, phi, ROLL_ACT, q0=q0, tol_inc=TOL_INC)
        if q is not None:
            return q
    return None


def yaw_real_rel(m):
    """Giro real del cubo respecto al robot (verdad de terreno, SOLO para medir), en [-45, 45) grados por la simetría del cubo."""
    import so101_manipulation as SM
    c, r = m.gt.get(SM.target_name()), m.gt.get('tb3_so101')
    if c is None or r is None:
        return None
    y = lambda q: math.atan2(2 * (q[6] * q[5] + q[3] * q[4]), 1 - 2 * (q[4] ** 2 + q[5] ** 2))
    return ((y(c) - y(r) + math.pi / 4) % (math.pi / 2)) - math.pi / 4


def tcp_now(m):
    q = [m.js.get(j, 0.0) for j in JOINTS]
    p, _ = fk(np.array(q))
    return np.array(p)


def run_trial(m, strat, rng_vals, args, tag='ensayo'):
    cx, cy, cyaw = rng_vals
    row = {k: '' for k in FIELDS}
    row.update(estrategia=strat, cubo_x=round(cx, 4), cubo_y=round(cy, 4), cubo_yaw_deg=round(math.degrees(cyaw), 1), carga_cpu=os.getloadavg()[0])
    # --- preparación: brazo en observación, pinza abierta, cubo en su sitio
    q_obs = m.tcp_to_q(OBS_XY[0], OBS_XY[1], Z_OBS, PHI_OBS)
    m.gripper(GRIP_OPEN); m.move_q(q_obs, 3.0)
    set_cube_pose(cx, cy, cyaw); m.spin_for(1.5)
    rec_dir = getattr(args, 'rec_dir', None)
    if rec_dir:
        m.start_recording(os.path.join(rec_dir, tag), cams=('wrist',))
    try:
        return grasp_cycle(m, strat, row, q_obs)
    finally:
        m.stop_recording()


def grasp_cycle(m, strat, row, q_obs, hold=False):
    """Observar -> estimar -> ejecutar la estrategia -> cerrar -> levantar -> medir. Lo usan el banco de pruebas y la misión completa."""
    t_sim0, t_wall0 = m.now(), time.time()
    est_list, dets = [], 0

    def see():
        nonlocal dets
        p, info = m.see_cube()
        if p is not None:
            dets += 1; est_list.append(p); m.mark(f'estimacion x={p[0]:.4f} y={p[1]:.4f}')
        else:
            m.mark('estimacion fallida: ' + str(info.get('motivo')))
        return p

    m.mark('observar')
    est = see()
    if est is None:
        row.update(exito=0, motivo='no detectado desde observación', detecciones=dets); return row
    row.update(est1_x=round(est[0], 4), est1_y=round(est[1], 4))
    gt = m.gt_cube_in_footprint()
    if gt is not None:
        row['err_est1_mm'] = round(1000 * float(np.hypot(est[0] - gt[0], est[1] - gt[1])), 1)

    target = est[:2].copy()
    phi_sel = None                                   # inclinación que permite llegar al cubo (plan B si está lejos o ladeado)
    for ph in (PHI, 70.0, 60.0):
        if q_agarre(m, np.array([target[0], target[1], CUBE_SIZE / 2]), ph) is not None:
            phi_sel = ph; break
    if phi_sel is None:
        row.update(exito=0, motivo='fuera de alcance (IK sin solución al agarrar)', detecciones=dets); return row
    row['phi_agarre'] = phi_sel
    cy = getattr(m, 'last_cube_yaw', None)
    if os.environ.get('SO101_ALINEAR', '1') == '0':   # experimento: sin alinear la muñeca
        cy = None
    roll = roll_alineado(m, np.array([target[0], target[1], CUBE_SIZE / 2]), phi_sel, cy)
    yr = yaw_real_rel(m)
    m.mark(f'muneca {math.degrees(roll):.0f} grados (cubo a {0 if cy is None else math.degrees(cy):.0f})')
    choque = []
    row.update(muneca_deg=round(math.degrees(roll), 1), cubo_yaw_est_deg='' if cy is None else round(math.degrees(cy), 1), cubo_yaw_real_deg='' if yr is None else round(math.degrees(yr), 1))

    def goto(xy, dz, dur=2.0):
        q = q_agarre(m, np.array([xy[0], xy[1], CUBE_SIZE / 2 + dz]), phi_sel)
        if q is None:
            print(f'  [IK] sin solución: xy=({xy[0]:.3f},{xy[1]:.3f}) dz={dz} phi={phi_sel}', flush=True)
            return None
        m.mark(f'ir_a x={xy[0]:.4f} y={xy[1]:.4f} dz={dz:.3f}')
        err = m.move_q(q, dur)
        if dz <= 0.03 and err > TOL_CHOQUE:            # bajando: la pinza no llegó porque chocó; no seguir empujando (levantaba el robot)
            m.mark(f'choque al bajar (error {err:.2f} rad)'); choque.append(err)
            qh = q_agarre(m, np.array([xy[0], xy[1], CUBE_SIZE / 2 + DZ_HOVER]), phi_sel)
            if qh is not None:
                m.move_q(qh, 1.5)
            return None
        return q

    m.gripper(GRIP_OPEN)
    if strat == 'ik_directa':                       # una detección y un solo movimiento (lazo abierto)
        if goto(target, DZ_HOVER, 2.5) is None or goto(target, DZ_GRASP, 2.0) is None:
            row.update(exito=0, motivo=f'choque al bajar ({choque[0]:.2f} rad)' if choque else 'IK sin solución'); return row
    elif strat == 'multietapa':                     # pre-agarre, vuelve a detectar desde más cerca y baja
        if goto(target, DZ_HOVER, 2.5) is None:
            row.update(exito=0, motivo='IK sin solución (pre-agarre)'); return row
        m.spin_for(0.5)
        e2 = see()
        if e2 is not None:
            target = e2[:2].copy()
        if goto(target, DZ_GRASP, 2.5) is None:
            row.update(exito=0, motivo=f'choque al bajar ({choque[0]:.2f} rad)' if choque else 'IK sin solución (agarre)'); return row
    elif strat == 'servovisual':                    # descenso en escalones con corrección proporcional x_{k+1} = x_k + 0.8 (x_est - x_k)
        for dz in (DZ_HOVER, 0.055, 0.03, DZ_GRASP):
            m.spin_for(0.4)
            e = see()
            if e is not None and np.linalg.norm(e[:2] - est[:2]) < 0.02:      # con la pinza cerca el cubo queda tapado: se descartan estimaciones atípicas
                target = target + 0.8 * (e[:2] - target)
            if goto(target, dz, 1.8) is None:
                row.update(exito=0, motivo=f'choque al bajar ({choque[0]:.2f} rad)' if choque else f'IK sin solución (dz={dz})'); return row

    if choque:
        m.gripper(GRIP_OPEN); m.move_q(q_obs, 2.5)
        row.update(exito=0, motivo=f'choque al bajar ({choque[0]:.2f} rad)', detecciones=dets); return row
    m.spin_for(0.6)
    # error del TCP respecto a la verdad de terreno en el momento del agarre
    gt = m.gt_cube_in_footprint(); tcp = tcp_now(m)
    if gt is not None:
        row['err_tcp_mm'] = round(1000 * float(np.hypot(tcp[0] - gt[0], tcp[1] - gt[1])), 1)
    if est_list:
        row['err_est_final_mm'] = round(1000 * float(np.hypot(est_list[-1][0] - gt[0], est_list[-1][1] - gt[1])), 1) if gt is not None else ''
    dbg = os.environ.get('MANIP_DEBUG')
    m.mark('cerrar_pinza')
    g0 = m.gripper(GRIP_CLOSE, effort=3.0, wait=2.0)
    if os.environ.get('MANIP_SAVE'):
        m.save_image(os.path.join(os.environ['MANIP_SAVE'], f'{strat}_closed.ppm'))
    if dbg:
        gg = m.gt_cube_in_footprint()
        print(f'  [dbg] tras cerrar: pinza={g0} z_cubo={None if gg is None else round(float(gg[2]),3)} tcp_z={tcp_now(m)[2]:.3f} q={[round(m.js.get(j,0),3) for j in JOINTS]}', flush=True)
    m.spin_for(1.0)                                   # deja que la pinza termine de apretar
    qlift = lift_q(m, tcp)
    m.mark('levantar')
    if qlift is not None:
        m.move_q(qlift, 4.0)                          # subida lenta: con 2.5 s el cubo a veces se resbalaba
    m.spin_for(2.0)
    m.mark('fin_levantado')
    gt = m.gt_cube_in_footprint(); tcp = tcp_now(m)
    if os.environ.get('MANIP_SAVE'):
        m.save_image(os.path.join(os.environ['MANIP_SAVE'], f'{strat}_lift.ppm'))
    if dbg:
        print(f'  [dbg] tras levantar: pinza={m.js.get("gripper_left_joint")} cubo={None if gt is None else [round(float(v),3) for v in gt]} tcp={[round(float(v),3) for v in tcp]} q={[round(m.js.get(j,0),3) for j in JOINTS]}', flush=True)
    ok = gt is not None and gt[2] > 0.08 and math.hypot(gt[0] - tcp[0], gt[1] - tcp[1]) < 0.07
    row.update(exito=int(ok), z_cubo_final=round(float(gt[2]), 3) if gt is not None else '',
               dist_cubo_tcp_mm=round(1000 * float(np.hypot(gt[0] - tcp[0], gt[1] - tcp[1])), 1) if gt is not None else '',
               motivo='' if ok else ('no levantó el cubo' if qlift is not None else 'IK sin solución (levantar)'), detecciones=dets,
               tiempo_sim_s=round(m.now() - t_sim0, 1), tiempo_real_s=round(time.time() - t_wall0, 1))
    if hold and ok:                                  # misión: lo lleva por encima del LiDAR y se queda sujetándolo
        qc = carry_q(m, tcp)
        if qc is not None:
            m.mark('transporte'); m.move_q(qc, 3.0); m.spin_for(1.0)
    if not (hold and ok):                            # hold=True (misión): se queda sujetando el cubo en la pose levantada
        m.gripper(GRIP_OPEN); m.move_q(q_obs, 2.5)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strategy', default='all'); ap.add_argument('--n', type=int, default=5); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--yaw-deg', type=float, default=10.0); ap.add_argument('--lat', type=float, default=0.06); ap.add_argument('--fwd-min', type=float, default=0.13); ap.add_argument('--fwd-max', type=float, default=0.19)
    ap.add_argument('--snap-dir', default=None); ap.add_argument('--snap-cams', default='vista_robot,vista_robot2'); ap.add_argument('--out', default='manip_resultados.csv'); ap.add_argument('--rec-dir', default=None, help='carpeta donde guardar videos y series temporales de cada ensayo')
    ap.add_argument('--phi', type=float, default=None); ap.add_argument('--margen', type=float, default=None); ap.add_argument('--d-prof', type=float, default=None); ap.add_argument('--roll', type=float, default=None)
    ap.add_argument('--grip-open', type=float, default=None); ap.add_argument('--grip-close', type=float, default=None)
    a = ap.parse_args()
    for k, v in (('PHI', a.phi), ('MARGEN', a.margen), ('D_PROF', a.d_prof), ('ROLL', a.roll), ('GRIP_OPEN', a.grip_open), ('GRIP_CLOSE', a.grip_close)):
        if v is not None: globals()[k] = v
    rclpy.init(); m = Manip()
    if a.snap_dir:
        os.makedirs(a.snap_dir, exist_ok=True); m.snap_dir = a.snap_dir; m.snap_cams = a.snap_cams.split(',')
    if not m.wait_data():
        print('sin datos del simulador (¿está lanzado y en el mismo dominio?)'); return 2
    strategies = STRATS if a.strategy == 'all' else a.strategy.split(',')
    rng = random.Random(a.seed)
    # mismas posiciones del cubo para todas las estrategias (comparación pareada)
    poses = [(rng.uniform(a.fwd_min, a.fwd_max), rng.uniform(-a.lat, a.lat), math.radians(rng.uniform(-a.yaw_deg, a.yaw_deg))) for _ in range(a.n)]
    new = not os.path.exists(a.out)
    with open(a.out, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new: w.writeheader()
        for i, p in enumerate(poses):
            for s in strategies:
                row = run_trial(m, s, p, a, tag=f'{s}_s{a.seed}_{i:02d}'); row.update(ensayo=i, semilla=a.seed)
                w.writerow({k: row.get(k, '') for k in FIELDS}); f.flush()
                print(s, i, 'ok' if row.get('exito') else 'FALLO', row.get('motivo', ''), 'err_est1=', row.get('err_est1_mm'), 'err_tcp=', row.get('err_tcp_mm'), flush=True)
    rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())

