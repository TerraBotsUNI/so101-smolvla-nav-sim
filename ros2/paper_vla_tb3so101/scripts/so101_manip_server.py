#!/usr/bin/python3
"""Servidor del brazo SO-101 (stack de cinemática). Un solo nodo que ofrece:
  acción    /so101/pick      (paper_vla_interfaces/action/Pick)  observar -> estimar con la cámara -> IK -> cerrar -> levantar
  servicio  /so101/observe   (std_srvs/Trigger)  lleva el brazo a la pose de observación con la pinza abierta
  servicio  /so101/stow      (std_srvs/Trigger)  pose de transporte (conserva lo que sujeta)
  servicio  /so101/release   (std_srvs/Trigger)  abre la pinza
  estrategia «vla»: la acción Pick la resuelve la política VLA (so101_vla.py + vla/servidor_politica.py)
  servicio  /so101/locate    (paper_vla_interfaces/srv/Locate)  ¿dónde está el cubo de color X? -> x, y en base_footprint
  servicio  /so101/ver       (std_srvs/Trigger)  observa y devuelve la posición estimada del cubo en base_footprint: "x y" (m)
  servicio  /so101/place     (std_srvs/Trigger)  baja el cubo sujeto al suelo delante del robot (place_x, place_y) y lo suelta
  topic     /so101/estado    (std_msgs/String)   etapa actual
Parámetro `strategy` (ik_directa | multietapa | servovisual) por defecto para la acción.
Las órdenes llegan por los hilos de ROS y se ejecutan en el hilo principal, que es el único que mueve el brazo."""
import os, queue, sys, threading
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rclpy
from rclpy.action import ActionServer, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import String
from std_srvs.srv import Trigger
from paper_vla_interfaces.action import Pick
from paper_vla_interfaces.srv import Locate
import so101_manipulation as SM
import so101_trial as T
from so101_manipulation import Manip


def place(m, px, py, q_obs):
    """Baja el cubo sujeto hasta el suelo en (px, py) de base_footprint (mismas posturas que el agarre, que deja el cubo entre las almohadillas), lo suelta, sube y vuelve a observación."""
    c = np.array([px, py, T.CUBE_SIZE / 2])
    phi = next((p for p in (T.PHI, 70.0, 60.0) if T.q_agarre(m, c, p) is not None), None)
    if phi is None:
        return False, 'IK sin solución al colocar'

    def go(dz, dur):
        q = T.q_agarre(m, c + np.array([0, 0, dz]), phi)
        if q is None:
            raise RuntimeError(f'IK sin solución dz={dz}')
        m.move_q(q, dur)

    m.mark('colocar_sobre'); go(T.DZ_HOVER, 3.0)
    m.mark('colocar_bajar'); go(0.004, 2.5); m.spin_for(0.5)
    m.mark('soltar'); m.gripper(T.GRIP_OPEN, wait=1.5); m.spin_for(0.5)
    m.mark('colocar_subir'); go(T.DZ_HOVER, 2.5)
    m.move_q(q_obs, 3.0)
    return True, 'cubo colocado'


class Job:
    def __init__(self, kind, **kw):
        self.kind, self.kw, self.done, self.result, self.stage = kind, kw, threading.Event(), None, 'en cola'


class Iface(Node):
    def __init__(self, jobs):
        super().__init__('so101_manipulator', parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.jobs = jobs
        cb = ReentrantCallbackGroup()
        self.declare_parameter('strategy', 'ik_directa')
        self.declare_parameter('place_x', 0.16)       # dónde deja el cubo, en base_footprint (m)
        self.declare_parameter('place_y', 0.0)
        self.declare_parameter('vla_puerto', 5555)    # servidor de la política VLA (vla/servidor_politica.py)
        self.declare_parameter('vla_t_max', 35.0)     # s de simulación por episodio VLA
        self.declare_parameter('vla_grabar_dir', '')   # carpeta donde grabar cada intento VLA (vacío = no grabar)
        self.estado = self.create_publisher(String, '/so101/estado', 10)
        for nm in ('observe', 'stow', 'release', 'place', 'ver'):
            self.create_service(Trigger, f'/so101/{nm}', lambda rq, rs, k=nm: self._srv(k, rs), callback_group=cb)
        self.create_service(Locate, '/so101/locate', self._locate, callback_group=cb)
        self.srv_pick = ActionServer(self, Pick, '/so101/pick', self._pick, goal_callback=self._goal, callback_group=cb)

    def _goal(self, g):
        s = g.strategy or self.get_parameter('strategy').value
        return GoalResponse.ACCEPT if (s in T.STRATS or s == 'vla') and (g.color or 'verde') in SM.COLORES else GoalResponse.REJECT

    def _locate(self, rq, rs):
        if (rq.color or 'verde') not in SM.COLORES:
            rs.success, rs.message = False, f'color desconocido: {rq.color}'
            return rs
        ok, msg = self._run(Job('ver', color=rq.color or 'verde'))
        rs.success, rs.message = ok, msg
        if ok:
            rs.x, rs.y = (float(v) for v in msg.split())
        return rs

    def _run(self, job, gh=None):
        self.jobs.put(job)
        last = None
        while not job.done.wait(0.2):
            if gh is not None and job.stage != last:
                last = job.stage
                fb = Pick.Feedback(); fb.stage = last
                gh.publish_feedback(fb)
        return job.result

    def _srv(self, kind, rs):
        ok, msg = self._run(Job(kind))
        rs.success, rs.message = ok, msg
        return rs

    def _pick(self, gh):
        g = gh.request
        s = g.strategy or self.get_parameter('strategy').value
        row = self._run(Job('pick', strategy=s, hold=g.hold, color=g.color or 'verde'), gh)
        res = Pick.Result()
        res.success = bool(row.get('exito'))
        res.message = row.get('motivo') or ('ok' if res.success else 'fallo')
        for k, a in (('z_cubo_final', 'cube_z'), ('err_est1_mm', 'est_error_mm'), ('tiempo_sim_s', 'duration_s')):
            try:
                setattr(res, a, float(row.get(k)))
            except (TypeError, ValueError):
                pass
        (gh.succeed if res.success else gh.abort)()
        return res


def main():
    rclpy.init()
    import signal                                     # Ctrl-C / TERM: salir YA (si no llegaban datos del simulador, el proceso quedaba colgado)
    signal.signal(signal.SIGINT, lambda *a: os._exit(0)); signal.signal(signal.SIGTERM, lambda *a: os._exit(0))
    jobs = queue.Queue()
    iface = Iface(jobs)
    m = Manip('so101_manip_driver')
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(iface)
    threading.Thread(target=ex.spin, daemon=True).start()
    iface.get_logger().info('esperando al simulador (cámara, joint_states)...')
    while not m.wait_data(timeout=5.0) and rclpy.ok():
        pass
    q_obs = m.tcp_to_q(T.OBS_XY[0], T.OBS_XY[1], T.Z_OBS, T.PHI_OBS)
    iface.get_logger().info('listo: acción /so101/pick, servicios /so101/{observe,stow,release,place,ver}')

    def say(s):
        iface.estado.publish(String(data=s))

    say('listo')
    try:
        bucle(jobs, m, iface, q_obs, say)
    except Exception:
        pass                                         # apagado (Ctrl-C / SIGTERM): el contexto de rclpy ya no es válido
    os._exit(0)                                      # no esperar al hilo del ejecutor: antes quedaban servidores huérfanos


def bucle(jobs, m, iface, q_obs, say):
    while rclpy.ok():
        try:
            job = jobs.get_nowait()
        except queue.Empty:
            rclpy.spin_once(m, timeout_sec=0.05)
            continue
        orig = m.mark
        try:
            say(job.kind)
            m.mark = lambda lab, j=job, o=orig: (setattr(j, 'stage', lab), say(lab), o(lab))
            if job.kind == 'observe':
                m.gripper(T.GRIP_OPEN)
                m.move_q(q_obs, 3.0)
                job.result = (True, 'en pose de observación')
            elif job.kind == 'ver':
                SM.TARGET['color'] = job.kw.get('color', 'verde')
                m.gripper(T.GRIP_OPEN)
                m.move_q(q_obs, 3.0)
                m.spin_for(0.5)
                p, info = m.see_cube()
                job.result = (True, f'{p[0]:.4f} {p[1]:.4f}') if p is not None else (False, str(info.get('motivo')))
            elif job.kind == 'stow':
                m.move_q(q_obs, 3.0)
                job.result = (True, 'pose de transporte')
            elif job.kind == 'release':
                m.gripper(T.GRIP_OPEN)
                job.result = (True, 'pinza abierta')
            elif job.kind == 'place':
                job.result = place(m, iface.get_parameter('place_x').value, iface.get_parameter('place_y').value, q_obs)
            elif job.kind == 'pick':
                SM.TARGET['color'] = job.kw.get('color', 'verde')
                m.gripper(T.GRIP_OPEN)
                m.move_q(q_obs, 3.0)
                m.spin_for(0.5)
                row = {k: '' for k in T.FIELDS}
                if job.kw['strategy'] == 'vla':                 # política VLA en otro proceso (Python 3.12, GPU)
                    import so101_vla
                    if getattr(m, 'cliente_vla', None) is None:
                        m.cliente_vla = so101_vla.ClienteVLA(puerto=iface.get_parameter('vla_puerto').value)
                    try:
                        job.result = so101_vla.vla_cycle(m, job.kw.get('color', 'verde'), row, q_obs, job.kw['hold'], m.cliente_vla,
                                                         t_max=iface.get_parameter('vla_t_max').value, grabar_dir=iface.get_parameter('vla_grabar_dir').value)
                    except (ConnectionError, OSError) as e:
                        m.cliente_vla = None; raise RuntimeError(f'sin servidor VLA: {e}')
                else:
                    job.result = T.grasp_cycle(m, job.kw['strategy'], row, q_obs, hold=job.kw['hold'])
        except Exception as e:                       # un fallo no tumba el servidor
            iface.get_logger().error(f'{job.kind}: {e!r}')
            job.result = {'exito': 0, 'motivo': repr(e)} if job.kind == 'pick' else (False, repr(e))
        finally:
            m.mark = orig
            say('listo')
            job.done.set()


if __name__ == '__main__':
    main()
