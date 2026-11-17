#!/usr/bin/python3
"""Dibuja un ensayo: arena, obstáculos (con radio del robot), ruta planificada y trayectoria real. Uso: plot_trial.py trace.json out.png"""
import json, math, os, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, yaml
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = yaml.safe_load(open(os.path.join(PKG, 'config', 'arena.yaml'), encoding='utf-8'))
d = json.load(open(sys.argv[1])); R = cfg['robot']['radius']
fig, ax = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [1.25, 1]})
a = ax[0]
for o in cfg['obstacles']:
    a.add_patch(plt.Circle((o['x'], o['y']), o['radius'], color='#d9591a', alpha=.9))
    a.add_patch(plt.Circle((o['x'], o['y']), o['radius'] + R, fill=False, ls=':', color='#d9591a'))
    a.text(o['x'], o['y'], o['name'], ha='center', va='center', fontsize=8, color='w')
if d.get('plan'):
    px, py = zip(*d['plan']); a.plot(px, py, '-', color='tab:blue', lw=2, label='ruta planificada (Smac)')
od = d['odom']
if od:
    a.plot([s[1] for s in od], [s[2] for s in od], '-', color='crimson', lw=1.6, label='trayectoria real')
    sc = a.scatter([s[1] for s in od], [s[2] for s in od], c=[s[0] for s in od], cmap='viridis', s=8, zorder=3)
    plt.colorbar(sc, ax=a, label='tiempo de simulación (s)', fraction=0.04)
a.plot(*cfg['robot']['start'][:2], 'ks', ms=9, label='inicio'); a.plot(d['goal'][0], d['goal'][1], 'g*', ms=18, label='meta')
a.add_patch(plt.Circle((d['goal'][0], d['goal'][1]), 0.15, fill=False, color='g'))
a.set_xlim(-1.0, 3.5); a.set_ylim(-1.2, 3.2); a.set_aspect('equal'); a.grid(alpha=.3); a.legend(loc='lower right', fontsize=8)
a.set_xlabel('x (m)'); a.set_ylabel('y (m)'); r = d['result']
a.set_title(f"{r['controller']}  estado={r['status']}  t={r['time_sim_s']} s  L={r['path_length_m']} m  error={r['final_error_m']} m  holgura mín={r['clearance_min_m']} m")
b = ax[1]; cm = d['cmd']
if cm:
    b.plot([c[0] for c in cm], [c[1] for c in cm], label='v lineal comandada (m/s)'); b.plot([c[0] for c in cm], [c[2] for c in cm], label='w comandada (rad/s)')
dist = [math.hypot(s[1] - d['goal'][0], s[2] - d['goal'][1]) for s in od]
b.plot([s[0] for s in od], dist, 'k--', label='distancia a la meta (m)'); b.axhline(0.15, color='g', ls=':')
b.set_xlabel('tiempo de simulación (s)'); b.grid(alpha=.3); b.legend(fontsize=8); b.set_title('órdenes y distancia a la meta')
fig.tight_layout(); fig.savefig(sys.argv[2], dpi=110); print('figura escrita', sys.argv[2])
