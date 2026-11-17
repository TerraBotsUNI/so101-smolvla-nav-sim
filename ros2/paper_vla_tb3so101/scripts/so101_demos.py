#!/usr/bin/python3
"""Generador de demostraciones para el VLA (formato intermedio; el conversor a LeRobot vive en ~/proyecto/paper_rover_vla_2025/vla/).
El experto clásico (cámara de muñeca + cinemática inversa) recoge el cubo pedido entre 3 cubos de colores barajados delante del robot,
igual que en la misión después del paso ACERCAR. Se graba a FPS fijos (reloj de simulación):
  <out>/ep_NNNNN/wrist.mp4, front.mp4   (256x256, un fotograma por paso; los graba so101_grabador.py en otro proceso)
  <out>/ep_NNNNN/estado.csv            (t, 5 articulaciones del brazo + pinza)  -> la acción del paso t es el estado del paso t+1
  <out>/ep_NNNNN/meta.json             (instrucción, color, éxito, poses de los cubos, estrategia, semilla)
El episodio va desde la pose de observación hasta el cubo levantado (sin soltar). Requiere: cinematica.launch.py (sin Nav2).
Uso: ros2 run paper_vla_tb3so101 so101_demos.py --n 200 --seed 1 --out ~/proyecto/paper_rover_vla_2025/demos/crudas"""
import argparse, json, math, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, numpy as np, rclpy
import so101_manipulation as SM
import so101_trial as T
from so101_manipulation import Manip, set_cube_pose, CUBE_SIZE

INGLES = {'rojo': 'red', 'verde': 'green', 'azul': 'blue'}
PLANTILLAS = ['pick up the {c} cube', 'grab the {c} cube', 'pick the {c} block', 'take the {c} cube']
JOINTS6 = list(SM.JOINTS) + ['gripper']


class Grabador:
    """Cliente del grabador persistente (so101_grabador.py --ctrl): un solo proceso por corrida con su propio temporizador a FPS de simulación
    (sin pausas por los cálculos del experto). Cada episodio: start(dir) escribe «GRABAR dir» y espera <dir>/listo; stop() escribe «PARAR»
    y espera <dir>/hecho. Si el grabador no responde, se reinicia el proceso una vez."""
    def __init__(self, m, fps=10):
        self.m, self.fps, self.p, self.d = m, fps, None, None
        self.ctrl = f'/tmp/so101_grabador_ctrl_{os.getpid()}.txt'

    def _orden(self, txt):
        tmp = self.ctrl + '.tmp'; open(tmp, 'w').write(txt); os.replace(tmp, self.ctrl)

    def _lanzar(self, log):
        import subprocess
        self.cerrar(); self._orden('PARAR inicial')
        self.p = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'so101_grabador.py'), '--ctrl', self.ctrl, '--fps', str(self.fps)],
                                  stdout=open(log, 'a'), stderr=subprocess.STDOUT)

    def start(self, d, espera=60, intentos=2):
        os.makedirs(d, exist_ok=True); self.d = d
        for k in range(intentos):
            if self.p is None or self.p.poll() is not None or k > 0:
                self._lanzar(os.path.join(os.path.dirname(os.path.abspath(d)), 'grabador_proceso.log'))
            for fn in ('listo', 'hecho'):
                if os.path.exists(os.path.join(d, fn)):
                    os.remove(os.path.join(d, fn))
            self._orden(f'GRABAR {d}')
            t0 = time.time()
            while not os.path.exists(os.path.join(d, 'listo')) and time.time() - t0 < espera:
                self.m.spin_for(0.2)
            if os.path.exists(os.path.join(d, 'listo')):
                return True
            self._orden(f'PARAR {d}')
        return False

    def stop(self):
        if self.d is None:
            return 0
        self._orden(f'PARAR {self.d}')
        t0 = time.time()
        while not os.path.exists(os.path.join(self.d, 'hecho')) and time.time() - t0 < 30 and self.p is not None and self.p.poll() is None:
            time.sleep(0.05)
        for fn in ('listo', 'hecho'):
            try:
                os.remove(os.path.join(self.d, fn))
            except OSError:
                pass
        try:
            return sum(1 for _ in open(os.path.join(self.d, 'estado.csv'))) - 1
        except Exception:
            return 0

    def cerrar(self):
        if self.p is not None and self.p.poll() is None:
            self._orden('SALIR')
            try:
                self.p.wait(timeout=10)
            except Exception:
                self.p.kill()
        self.p = None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=20); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--out', default=os.path.expanduser('~/proyecto/paper_rover_vla_2025/demos/crudas'))
    ap.add_argument('--strategy', default='ik_directa'); ap.add_argument('--fps', type=int, default=10)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    rclpy.init(); m = Manip('so101_demos')
    if not m.wait_data():
        print('sin datos del simulador'); return 2
    g = Grabador(m, a.fps)
    q_obs = m.tcp_to_q(T.OBS_XY[0], T.OBS_XY[1], T.Z_OBS, T.PHI_OBS)
    os.makedirs(a.out, exist_ok=True)
    k0 = 1 + max([int(d[3:]) for d in os.listdir(a.out) if d.startswith('ep_') and d[3:].isdigit()] or [-1])   # continúa tras el último episodio
    ok_total = 0
    import signal

    class Colgado(Exception):
        pass

    def _alarma(*_):
        raise Colgado()
    signal.signal(signal.SIGALRM, _alarma)

    def pose_robot():
        """Pose real del robot en el mundo (x, y, z, guiñada), de la verdad de terreno de Gazebo."""
        m.spin_for(0.3)
        x, y, z, qx, qy, qz, qw = m.gt['tb3_so101']
        return x, y, z, math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))

    P0 = pose_robot()                                 # pose inicial: se vuelve a ella si el robot deriva entre episodios

    def al_mundo(poses, p):
        """Poses de los cubos dadas respecto al robot (x adelante, y izquierda, guiñada) -> mundo."""
        x0, y0, _, th = p; c, s_ = math.cos(th), math.sin(th)
        return {k: (x0 + c * x - s_ * y, y0 + s_ * x + c * y, yaw + th) for k, (x, y, yaw) in poses.items()}

    def cubos_en_su_sitio(poses, tol=0.015):
        """Verdad de terreno (solo para preparar la escena): con la máquina cargada el servicio de Gazebo que mueve los cubos a veces no responde
        y el cubo quedaba fuera de la vista ("no detectado desde observación")."""
        m.spin_for(0.5)
        for c, (x, y, _) in poses.items():
            g = m.gt.get(SM.COLORES[c][1])
            if g is None or abs(g[0] - x) > tol or abs(g[1] - y) > tol:
                return False
        return True

    for i in range(a.n):
        signal.alarm(300)                            # si Gazebo se congela, el episodio no termina: se sale para que el colector relance la simulación
        try:
            color = rng.choice(list(SM.COLORES)); SM.TARGET['color'] = color
            # objetivo cerca de donde lo deja el paso ACERCAR; los otros dos a +-SEP en lateral (barajados), con ruido
            tx, ty = rng.uniform(0.14, 0.18), rng.uniform(-0.025, 0.025)
            otros = [c for c in SM.COLORES if c != color]; rng.shuffle(otros)
            lados = [1, -1]; rng.shuffle(lados)
            if os.environ.get('SO101_DISPOSICION') == 'mision':   # 15-nov (diagnóstico de fallos): el pedido en cualquier posición de la fila, como en la misión
                pos = rng.randrange(3)                              # 0: vecinos a la derecha; 1: uno a cada lado; 2: vecinos a la izquierda
                lados = {0: [-1, -2], 1: lados, 2: [1, 2]}[pos]
            poses = {color: (tx, ty, math.radians(rng.uniform(-40, 40)))}
            for c, s in zip(otros, lados):
                poses[c] = (rng.uniform(0.13, 0.19), ty + s * rng.uniform(0.125, 0.145), math.radians(rng.uniform(-40, 40)))
            m.gripper(T.GRIP_OPEN); m.move_q(q_obs, 3.0)
            # El robot deriva poco a poco entre episodios (empujones del brazo y de los cubos): tras ~10 episodios los cubos, colocados en
            # coordenadas fijas del mundo, ya no quedaban delante de la cámara («no detectado desde observación», 12-nov). Se devuelve el robot
            # a su pose inicial si se movió más de 2 cm o 2° y los cubos se colocan respecto a la pose REAL del robot.
            p = pose_robot()
            if math.hypot(p[0] - P0[0], p[1] - P0[1]) > 0.02 or abs(math.remainder(p[3] - P0[3], 2 * math.pi)) > math.radians(2):
                print(f'[{k0 + i}] robot desplazado {100 * math.hypot(p[0] - P0[0], p[1] - P0[1]):.1f} cm / {math.degrees(math.remainder(p[3] - P0[3], 2 * math.pi)):.1f}°: lo devuelvo a su pose inicial', flush=True)
                set_cube_pose(P0[0], P0[1], P0[3], z=P0[2] + 0.005, name='tb3_so101'); m.spin_for(1.5); p = pose_robot()
            poses_w = al_mundo(poses, p)
            for intento in range(3):
                for c, (x, y, yaw) in poses_w.items():
                    set_cube_pose(x, y, yaw, name=SM.COLORES[c][1])
                m.spin_for(1.5)
                if cubos_en_su_sitio(poses_w):
                    break
            else:
                print(f'[{k0 + i}] los cubos no quedaron en su sitio; salto el episodio', flush=True); signal.alarm(0); continue
            task = rng.choice(PLANTILLAS).format(c=INGLES[color])
            d = os.path.join(a.out, f'ep_{k0 + i:05d}')
            t_wall = time.time()
            if not g.start(d):
                g.stop(); print('el grabador no arrancó (¿publican las cámaras?); salto el episodio', flush=True)
                fallos_grab = locals().get('fallos_grab', 0) + 1
                if fallos_grab >= 3:
                    print('3 fallos seguidos del grabador: me detengo', flush=True); break
                continue
            fallos_grab = 0
            row = T.grasp_cycle(m, a.strategy, {k: '' for k in T.FIELDS}, q_obs, hold=True)
            n = g.stop()
            ok = bool(row.get('exito'))
            signal.alarm(0)
            meta = dict(instruccion=task, color=color, exito=ok, motivo=row.get('motivo', ''), estrategia=a.strategy, semilla=a.seed, fps=a.fps,
                        pasos=n, cubos={c: [round(v, 4) for v in p] for c, p in poses.items()}, tiempo_real_s=round(time.time() - t_wall, 1),
                        articulaciones=JOINTS6, camaras=['wrist', 'scene', 'front'],
                        diagnostico={k: row.get(k) for k in ('err_est1_mm', 'err_est_final_mm', 'err_tcp_mm', 'z_cubo_final', 'dist_cubo_tcp_mm', 'phi_agarre', 'detecciones')})
            json.dump(meta, open(os.path.join(d, 'meta.json'), 'w'), indent=1, ensure_ascii=False)
            ok_total += ok
            print(f'[{k0 + i}] "{task}": {"OK" if ok else "FALLO " + str(row.get("motivo"))} ({n} pasos)', flush=True)
            m.gripper(T.GRIP_OPEN); m.move_q(q_obs, 2.5)       # suelta (fuera del episodio)
        except Colgado:
            print(f'[{k0 + i}] episodio colgado más de 300 s de tiempo real (Gazebo congelado); salgo para que el colector relance la simulación', flush=True)
            try:
                g.stop()
            except Exception:
                pass
            os._exit(3)
    g.cerrar()
    print(f'{ok_total}/{a.n} episodios exitosos -> {a.out}')
    rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
