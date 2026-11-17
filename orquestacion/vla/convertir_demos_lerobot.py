#!/usr/bin/env python3
"""Convierte las demostraciones crudas del SO-101 (las graba `ros2 run paper_vla_tb3so101 so101_demos.py`) a un LeRobotDataset (LeRobot 0.6.1).
Se ejecuta con el Python 3.12 del proyecto (NO con el de ROS):
  ~/proyecto/paper_rover_vla_2025/env/bin/python convertir_demos_lerobot.py \
      --crudas ~/proyecto/paper_rover_vla_2025/demos/crudas --salida ~/proyecto/paper_rover_vla_2025/demos/lerobot_so101_cubos
Por cada paso t: observation.images.wrist / .front (256x256), observation.state (6: 5 articulaciones + pinza), action (6) = estado del paso t+1 (con --pinza-orden, la pinza = orden del experto: 0.85 abrir / 0.0 cerrar), task = instrucción.
Solo se usan los episodios con éxito (meta.json -> exito)."""
import argparse, json, os, shutil, sys
import cv2
import numpy as np


def leer_video(p):
    cap = cv2.VideoCapture(p); fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        fr.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    return fr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--crudas', required=True, nargs='+', help='una o varias carpetas con episodios ep_NNNNN'); ap.add_argument('--salida', required=True)
    ap.add_argument('--repo-id', default='local/so101_cubos_colores'); ap.add_argument('--incluir-fallos', action='store_true')
    ap.add_argument('--pinza-orden', action='store_true', help='acción de la pinza = ORDEN del experto (0.85 abierta hasta que empieza a cerrar, luego 0.0 = cerrar), no la posición medida')
    a = ap.parse_args()
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    eps = [os.path.join(c, d) for c in a.crudas for d in sorted(os.listdir(c)) if d.startswith('ep_')]
    metas = {d: json.load(open(os.path.join(d, 'meta.json'))) for d in eps if os.path.exists(os.path.join(d, 'meta.json'))}
    usar = [d for d, mt in metas.items() if mt['exito'] or a.incluir_fallos]
    if not usar:
        print('no hay episodios utilizables'); return 1
    m0 = metas[usar[0]]; nombres = m0['articulaciones']; fps = m0['fps']
    features = {
        'observation.images.wrist': {'dtype': 'video', 'shape': (256, 256, 3), 'names': ['height', 'width', 'channels']},
        'observation.images.scene': {'dtype': 'video', 'shape': (256, 256, 3), 'names': ['height', 'width', 'channels']},
        'observation.state': {'dtype': 'float32', 'shape': (len(nombres),), 'names': nombres},
        'action': {'dtype': 'float32', 'shape': (len(nombres),), 'names': nombres},
    }
    if os.path.exists(a.salida):
        shutil.rmtree(a.salida)
    ds = LeRobotDataset.create(repo_id=a.repo_id, fps=fps, features=features, root=a.salida, robot_type='so101_follower', use_videos=True)
    n_pasos = 0
    for d in usar:
        p = d
        est = np.loadtxt(os.path.join(p, 'estado.csv'), delimiter=',', skiprows=1, ndmin=2)[:, 1:].astype(np.float32)
        cam2 = 'scene.mp4' if os.path.exists(os.path.join(p, 'scene.mp4')) else 'front.mp4'      # cámara de escena del mástil (desde el 12-nov)
        wr, fr = leer_video(os.path.join(p, 'wrist.mp4')), leer_video(os.path.join(p, cam2))
        T = min(len(est), len(wr), len(fr))
        if T < 5:
            print('salto', d, '(muy corto)'); continue
        acc = est[1:T].copy()
        if a.pinza_orden:                     # 14-nov: el experto ordena cerrar del todo (GRIP_CLOSE 0.0); la posición medida se queda en el cubo (~0.45/0.28)
            g = acc[:, -1]; ic = np.flatnonzero(g < 0.80)
            acc[:, -1] = 0.85
            if len(ic):
                acc[ic[0]:, -1] = 0.0
        for t in range(T - 1):
            ds.add_frame({'observation.images.wrist': wr[t], 'observation.images.scene': fr[t],
                          'observation.state': est[t], 'action': acc[t], 'task': metas[d]['instruccion']})
        ds.save_episode(); n_pasos += T - 1
        print(f'{d}: {T - 1} pasos  "{metas[d]["instruccion"]}"', flush=True)
    ds.finalize()
    print(f'listo: {len(usar)} episodios, {n_pasos} pasos -> {a.salida}')


if __name__ == '__main__':
    sys.exit(main())
