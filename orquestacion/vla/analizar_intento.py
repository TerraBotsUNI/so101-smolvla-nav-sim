#!/usr/bin/env python3
"""Diagnóstico de un intento VLA grabado: hoja de fotogramas (muñeca y frontal cada ~3 s) y articulaciones del intento frente a una demostración
del experto del mismo color. Uso: python3 analizar_intento.py <carpeta_intento> <carpeta_demos> <salida_prefijo>"""
import glob, json, os, sys
import cv2, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

it, demos, out = sys.argv[1], sys.argv[2], sys.argv[3]
meta = json.load(open(os.path.join(it, 'meta.json')))


def frames(p, cada=30, n=8):
    cap = cv2.VideoCapture(p); fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        fr.append(f)
    return [fr[min(i, len(fr) - 1)] for i in range(0, cada * n, cada)] if fr else []


filas = []
for cam in ('wrist', 'front'):
    fs = frames(os.path.join(it, cam + '.mp4'))
    if fs:
        for k, f in enumerate(fs):
            cv2.putText(f, f'{3 * k} s', (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        filas.append(np.hstack(fs))
if filas:
    cv2.imwrite(out + '_fotogramas.jpg', np.vstack(filas))

A = np.loadtxt(os.path.join(it, 'acciones.csv'), delimiter=',', skiprows=1, ndmin=2)
cands = [d for d in sorted(glob.glob(os.path.join(demos, 'ep_*'))) if os.path.exists(os.path.join(d, 'meta.json'))]
demo = next((d for d in cands if json.load(open(os.path.join(d, 'meta.json'))).get('color') == meta['color'] and json.load(open(os.path.join(d, 'meta.json'))).get('exito')), None)
E = np.loadtxt(os.path.join(demo, 'estado.csv'), delimiter=',', skiprows=1, ndmin=2) if demo else None
nombres = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']
fig, axs = plt.subplots(2, 3, figsize=(12, 6), sharex=True)
for j, ax in enumerate(axs.flat):
    t = A[:, 0] - A[0, 0]
    ax.plot(t, A[:, 1 + j], label='VLA: estado medido', color='#2b6cb0')
    ax.plot(t, A[:, 7 + j], label='VLA: acción pedida', color='#dd6b20', lw=0.8)
    if E is not None:
        ax.plot(E[:, 0] - E[0, 0], E[:, 1 + j], label='experto (demostración)', color='#2f855a', ls='--')
    ax.set_title(nombres[j], fontsize=9); ax.grid(alpha=0.3)
axs[0, 0].legend(fontsize=7); fig.suptitle(f"«{meta['instruccion']}» — éxito: {meta['exito']} (cubo z = {meta['z_cubo']:.3f} m)", fontsize=10)
fig.supxlabel('tiempo (s)'); fig.tight_layout(); fig.savefig(out + '_articulaciones.png', dpi=110)
print('ok', out, '| demo de referencia:', demo)
