#!/usr/bin/env python3
"""Servidor GENÉRICO de políticas de LeRobot (15-nov: copia de servidor_politica.py que carga cualquier tipo, p. ej. ACT o SmolVLA, según config.json).
Servidor de la política VLA (SmolVLA ajustado) para el robot simulado. Corre con el Python 3.12 del proyecto (LeRobot); el robot (ROS 2,
Python 3.10) le pregunta por TCP «con estas imágenes, este estado y esta instrucción, ¿qué hago?» y recibe la acción (6 posiciones articulares).
Uso: env/bin/python vla/servidor_politica.py --modelo vla/entrenos/<entreno>/checkpoints/008000/pretrained_model [--puerto 5555] [--n-acciones 25]
Protocolo (cada mensaje): 4 bytes big-endian con la longitud de la cabecera JSON + cabecera JSON + datos binarios.
  petición  {"tipo": "reset"}  ó  {"tipo": "accion", "tarea": str, "estado": [6]} seguida de 2 imágenes RGB uint8 de 256x256 (por defecto muñeca y escena; campo opcional "camaras")
  respuesta {"ok": true, "accion": [6], "ms": tiempo_de_inferencia}
"""
import argparse, json, os, socket, struct, time
# 14-nov: limitar los hilos de CPU (OpenMP/MKL/PyTorch). La inferencia va en la GPU; con la VM a 40 vCPU PyTorch abría ~200 hilos que
# competían con las simulaciones de Gazebo (hasta 8 núcleos y mucho tiempo de sistema). VLA_HILOS (4 por defecto) lo cambia.
for _v in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ.setdefault(_v, os.environ.get('VLA_HILOS', '4'))
import numpy as np
import torch
torch.set_num_threads(int(os.environ.get('VLA_HILOS', '4'))); torch.set_num_interop_threads(2)
from lerobot.policies.factory import get_policy_class
from lerobot.policies.factory import make_pre_post_processors
from lerobot.common.control_utils import predict_action

TAM = 256 * 256 * 3


def recibir(con, n):
    b = bytearray()
    while len(b) < n:
        p = con.recv(n - len(b))
        if not p:
            raise ConnectionError('cliente desconectado')
        b.extend(p)
    return bytes(b)


def enviar(con, d):
    h = json.dumps(d).encode(); con.sendall(struct.pack('>I', len(h)) + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modelo', required=True); ap.add_argument('--puerto', type=int, default=5555)
    ap.add_argument('--n-acciones', type=int, default=25, help='acciones del bloque que se ejecutan antes de volver a inferir (máx. 50)')
    a = ap.parse_args()
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    tipo = json.load(open(os.path.join(a.modelo, 'config.json')))['type']
    pol = get_policy_class(tipo).from_pretrained(a.modelo).to(dev); pol.eval()
    print('tipo de política:', tipo, flush=True)
    pol.config.n_action_steps = min(a.n_acciones, pol.config.chunk_size)
    pre, post = make_pre_post_processors(pol.config, pretrained_path=a.modelo)
    print(f'modelo cargado en {dev}: {a.modelo} | acciones por inferencia: {pol.config.n_action_steps}', flush=True)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', a.puerto)); srv.listen(1)
    print(f'escuchando en 127.0.0.1:{a.puerto}', flush=True)
    while True:
        con, _ = srv.accept(); con.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print('cliente conectado', flush=True)
        try:
            while True:
                (n,) = struct.unpack('>I', recibir(con, 4)); h = json.loads(recibir(con, n))
                if h['tipo'] == 'reset':
                    pol.reset(); enviar(con, {'ok': True}); continue
                wr = np.frombuffer(recibir(con, TAM), np.uint8).reshape(256, 256, 3)
                fr = np.frombuffer(recibir(con, TAM), np.uint8).reshape(256, 256, 3)
                c1, c2 = h.get('camaras', ['wrist', 'front'])          # nombres de las cámaras tal como se entrenó (muñeca + escena desde el 12-nov)
                obs = {f'observation.images.{c1}': wr, f'observation.images.{c2}': fr, 'observation.state': np.asarray(h['estado'], np.float32)}
                t0 = time.time()
                acc = predict_action(obs, pol, dev, pre, post, use_amp=False, task=h['tarea'], robot_type='so101_follower')
                enviar(con, {'ok': True, 'accion': [float(v) for v in acc.squeeze().tolist()], 'ms': round(1000 * (time.time() - t0), 1)})
        except (ConnectionError, BrokenPipeError, struct.error) as e:
            print('cliente desconectado:', e, flush=True)
        finally:
            con.close()


if __name__ == '__main__':
    main()
