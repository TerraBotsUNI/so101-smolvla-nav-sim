#!/usr/bin/python3
"""Nodo grabador de episodios (proceso aparte, para que los cálculos del experto no le quiten pasos).
Con un temporizador a --fps en TIEMPO DE SIMULACIÓN guarda la última imagen de la cámara de muñeca y la frontal (256x256, MP4)
y el estado articular (5 articulaciones + pinza) en <dir>/estado.csv. Crea <dir>/listo al estar recibiendo datos y <dir>/hecho al cerrar.
Un solo proceso por corrida (desde el 12-nov): lanzar un proceso por episodio hacía que, con la máquina cargada, a veces el proceso
nuevo no descubriera la simulación (no recibía nada) y se perdían episodios.
Lo lanza so101_demos.py; también sirve suelto:  ros2 run paper_vla_tb3so101 so101_grabador.py --dir /tmp/ep"""
import argparse, os, signal, sys, time
import cv2, numpy as np, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, JointState

JOINTS6 = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']


class Grabador(Node):
    """Se suscribe una sola vez (cámaras + articulaciones) y graba episodios a demanda: empezar(dir) / parar()."""
    def __init__(self, fps, size):
        super().__init__('so101_grabador', parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.fps, self.size, self.img, self.js = fps, size, {}, {}
        self.d, self.vw, self.rows, self.listo = None, {}, [], False
        # Imágenes con QoS de sensores (best effort): con QoS fiable, un suscriptor que llega tarde a veces no recibía las imágenes grandes
        q = qos_profile_sensor_data
        self.create_subscription(Image, '/wrist_camera/image_raw', lambda m: self.img.__setitem__('wrist', m), q)
        self.create_subscription(Image, '/camera/image_raw', lambda m: self.img.__setitem__('front', m), q)
        self.create_subscription(Image, '/scene_camera/image_raw', lambda m: self.img.__setitem__('scene', m), q)
        self.create_subscription(JointState, '/joint_states', lambda m: self.js.update(zip(m.name, m.position)), 10)
        self.create_timer(1.0 / fps, self.tick)

    def empezar(self, d):
        os.makedirs(d, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.vw = {c: cv2.VideoWriter(os.path.join(d, f'{c}.mp4'), fourcc, self.fps, (self.size, self.size)) for c in ('wrist', 'scene', 'front')}
        self.d, self.rows, self.listo = d, [], False

    def tick(self):
        if self.d is None or len(self.img) < 3 or not all(j in self.js for j in JOINTS6):
            return
        if not self.listo:
            open(os.path.join(self.d, 'listo'), 'w').close(); self.listo = True
        for c in ('wrist', 'scene', 'front'):
            m = self.img[c]
            rgb = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3)
            self.vw[c].write(cv2.cvtColor(cv2.resize(rgb, (self.size, self.size), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
        self.rows.append([round(self.get_clock().now().nanoseconds * 1e-9, 3)] + [round(float(self.js[j]), 5) for j in JOINTS6])

    def parar(self):
        if self.d is None:
            return 0
        for w in self.vw.values():
            w.release()
        with open(os.path.join(self.d, 'estado.csv'), 'w') as f:
            f.write('t_sim,' + ','.join(JOINTS6) + '\n')
            for r in self.rows:
                f.write(','.join(str(v) for v in r) + '\n')
        n, d = len(self.rows), self.d
        if n == 0:                                   # diagnóstico: qué entrada no llegó nunca
            falta = [c for c in ('wrist', 'scene', 'front') if c not in self.img] + [j for j in JOINTS6 if j not in self.js]
            print(f'sin datos de: {falta} | reloj de simulación: {self.get_clock().now().nanoseconds * 1e-9:.1f} s', flush=True)
        print(f'grabados {n} pasos en {d}', flush=True)
        open(os.path.join(d, 'hecho'), 'w').write(str(n))
        self.d, self.vw = None, {}
        return n


def main():
    """Modo persistente (--ctrl, lo usa so101_demos.py): lee órdenes de un archivo: «GRABAR <dir>» / «PARAR» / «SALIR».
    Termina solo si muere el proceso padre. Modo suelto (--dir): graba un episodio hasta Ctrl-C."""
    ap = argparse.ArgumentParser(); ap.add_argument('--dir'); ap.add_argument('--ctrl'); ap.add_argument('--fps', type=int, default=10); ap.add_argument('--size', type=int, default=256)
    a, _ = ap.parse_known_args()
    rclpy.init(); g = Grabador(a.fps, a.size)
    parar = []
    signal.signal(signal.SIGINT, lambda *x: parar.append(1)); signal.signal(signal.SIGTERM, lambda *x: parar.append(1))
    if a.dir:
        g.empezar(a.dir)
        while not parar:
            rclpy.spin_once(g, timeout_sec=0.02)
        g.parar(); os._exit(0)
    padre, ult, t_ctrl = os.getppid(), '', 0.0
    print(f'grabador persistente listo (control: {a.ctrl})', flush=True)
    while not parar and os.getppid() == padre:
        rclpy.spin_once(g, timeout_sec=0.02)
        if time.time() - t_ctrl < 0.05:
            continue
        t_ctrl = time.time()
        try:
            orden = open(a.ctrl).read().strip()
        except OSError:
            continue
        if orden == ult:
            continue
        ult = orden
        if orden.startswith('GRABAR '):
            g.parar(); g.empezar(orden[7:])
        elif orden.startswith('PARAR'):
            g.parar()
        elif orden == 'SALIR':
            break
    g.parar(); os._exit(0)


if __name__ == '__main__':
    sys.exit(main())
