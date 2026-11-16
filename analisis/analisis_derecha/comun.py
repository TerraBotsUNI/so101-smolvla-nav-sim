# Utilidades comunes del diagnostico (FK copiada de so101_kinematics.py; solo lectura de datos)
import os, glob, json, math
import numpy as np, pandas as pd
CADENA = [
    ('shoulder_pan',  (0.0388353, -8.97657e-09, 0.0624),       (3.14159, 4.18253e-17, -3.14159)),
    ('shoulder_lift', (-0.0303992, -0.0182778, -0.0542),       (-1.5708, -1.5708, 0.0)),
    ('elbow_flex',    (-0.11257, -0.028, 1.73763e-16),         (-3.63608e-16, 8.74301e-16, 1.5708)),
    ('wrist_flex',    (-0.1349, 0.0052, 3.62355e-17),          (4.02456e-15, 8.67362e-16, -1.5708)),
    ('wrist_roll',    (5.55112e-17, -0.0611, 0.0181),          (1.5708, 0.0486795, 3.14159)),
]
TOOL = ((-0.0079, -0.000218121, -0.0981274), (0.0, 3.14159, 0.0))
MONTAJE = np.array([-0.15, 0.0, 0.101])
JAW_C = np.array([0.0202, 0.0188, -0.0234]); JAW_AX = np.array([0.0, -1.0, 0.0]); TCP_L = np.array(TOOL[0])
J5 = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll']
J6 = J5 + ['gripper']
D_PROF, MARGEN, GRIP_OPEN, CUBE = 0.016, 0.018, 0.85, 0.04


def _rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]); Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]]); Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def _T(xyz, rpy):
    T = np.eye(4); T[:3, :3] = _rpy(*rpy); T[:3, 3] = xyz; return T


def _Rz(q):
    c, s = np.cos(q), np.sin(q); T = np.eye(4); T[0, 0], T[0, 1], T[1, 0], T[1, 1] = c, -s, s, c; return T


def fk_all(q):
    T = np.eye(4); T[:3, 3] = MONTAJE; out = []
    for (n, xyz, rpy), qi in zip(CADENA, q):
        T = T @ _T(xyz, rpy) @ _Rz(qi); out.append(T.copy())
    out.append(T @ _T(*TOOL)); return out


def fk(q):
    Ts = fk_all(q); p = Ts[-1][:3, 3]; mu = Ts[4][:3, 3]; a = p - mu; a = a / np.linalg.norm(a); return p, a


def _rod(ax, t):
    ax = ax / np.linalg.norm(ax); K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K


def jaw_gap(q, g=GRIP_OPEN):
    Rg = fk_all(q)[4][:3, :3]; p = JAW_C + _rod(JAW_AX, g) @ (TCP_L - JAW_C); return Rg @ (p - TCP_L)


def centro_agarre(q):
    """Inversa de la formula del experto: tcp = centro + D_PROF*a - MARGEN*u  ->  centro = tcp - D_PROF*a + MARGEN*u"""
    p, a = fk(q); u = jaw_gap(q); u = u / np.linalg.norm(u)
    return p - D_PROF * a + MARGEN * u, p, a, u


def wrap45(deg):
    return ((deg + 45.0) % 90.0) - 45.0


def parse_cubos(s):
    d = {}
    for it in s.split(';'):
        c, r = it.split(':'); d[c] = tuple(float(v) for v in r.split(','))
    return d


def metricas(q6, t, col_cmd=None, cubo=None):
    """q6: N x 6 estado medido; col_cmd: orden de pinza (accion del VLA) o None (demos: se usa el estado medido).
    cubo: (x, y, yaw_deg) del cubo pedido en base_footprint."""
    N = len(q6); g = q6[:, 5]
    tcp = np.array([fk(q6[i, :5])[0] for i in range(N)])
    r = dict(pasos=N, dur=float(t[-1] - t[0]))
    if col_cmd is not None:
        cerr = col_cmd < 0.65
        ic = np.flatnonzero(cerr)
        r['n_cambios'] = int(np.sum(np.diff(cerr.astype(int)) != 0))
        r['pasos_cerrar'] = int(cerr.sum())
    else:
        ic = np.flatnonzero(g < 0.80); r['n_cambios'] = 1 if len(ic) else 0
    if len(ic) == 0:
        r.update(i_cierre=-1, z_min=float(tcp[:, 2].min())); return r, tcp
    i0 = int(ic[0]); r['i_cierre'] = i0; r['t_cierre'] = float(t[i0] - t[0])
    c, p, a, u = centro_agarre(q6[i0, :5])
    r.update(tcp_x=p[0], tcp_y=p[1], tcp_z=p[2], ag_x=c[0], ag_y=c[1], ag_z=c[2], phi=float(np.degrees(np.arcsin(-a[2]))),
             u_az=float(np.degrees(np.arctan2(u[1], u[0]))), u_z=float(u[2]), roll=float(q6[i0, 4]), pan=float(q6[i0, 0]))
    k = min(N - 1, i0 + 3); k0 = max(0, i0 - 3)
    r['vel_cierre'] = float(np.abs(q6[k, :5] - q6[k0, :5]).max() / (t[k] - t[k0] + 1e-9))
    seg = g[i0 + 15:i0 + 30] if N > i0 + 15 else g[i0:]
    r['g_meseta'] = float(np.median(seg)) if len(seg) else float(g[-1])
    r['g_min'] = float(g[i0:].min()); r['g_fin'] = float(g[-1])
    z0 = p[2]; zs = tcp[i0:, 2]
    il = np.flatnonzero(zs > z0 + 0.015)
    r['i_levanta'] = int(i0 + il[0]) if len(il) else -1
    r['espera_cierre_levanta'] = float(t[i0 + il[0]] - t[i0]) if len(il) else float('nan')
    r['z_max_tras'] = float(zs.max()); r['z_fin'] = float(tcp[-1, 2]); r['z_min'] = float(tcp[:, 2].min())
    if len(il):
        r['g_en_levantado'] = float(np.median(g[i0 + il[0]:]))
    if cubo is not None:
        cx, cy, cyaw = cubo
        ex, ey = c[0] - cx, c[1] - cy
        r.update(err_x=ex, err_y=ey, err_xy=float(math.hypot(ex, ey)), err_u=float(ex * u[0] + ey * u[1]),
                 err_n=float(-ex * u[1] + ey * u[0]), err_yaw=float(wrap45(r['u_az'] - cyaw)))
    return r, tcp
