#!/usr/bin/python3
"""Cinemática del SO-101 montado en el TurtleBot3 (versión 2 del paper). La directa sale del URDF oficial (so101_new_calib.urdf);
la inversa es numérica (mínimos cuadrados amortiguados) con límites articulares, porque el brazo no tiene una forma cerrada sencilla (ejes con desfases).
Marco de trabajo: base_footprint. Montaje (tb3_so101_fortress.urdf.xacro): base_footprint -> base_link (0,0,0.010) -> so101_base_link (-0.15, 0, 0.091)."""
import numpy as np

# (nombre, xyz, rpy) de cada articulación en el orden de la cadena base -> herramienta (URDF oficial)
CADENA = [
    ('shoulder_pan',  (0.0388353, -8.97657e-09, 0.0624),       (3.14159, 4.18253e-17, -3.14159)),
    ('shoulder_lift', (-0.0303992, -0.0182778, -0.0542),       (-1.5708, -1.5708, 0.0)),
    ('elbow_flex',    (-0.11257, -0.028, 1.73763e-16),         (-3.63608e-16, 8.74301e-16, 1.5708)),
    ('wrist_flex',    (-0.1349, 0.0052, 3.62355e-17),          (4.02456e-15, 8.67362e-16, -1.5708)),
    ('wrist_roll',    (5.55112e-17, -0.0611, 0.0181),          (1.5708, 0.0486795, 3.14159)),
]
TOOL = ((-0.0079, -0.000218121, -0.0981274), (0.0, 3.14159, 0.0))      # gripper_frame_joint (fija, hija de gripper_link)
LIMITES = {'shoulder_pan': (-1.91986, 1.91986), 'shoulder_lift': (-1.74533, 1.74533), 'elbow_flex': (-1.69, 1.69),
           'wrist_flex': (-1.65806, 1.65806), 'wrist_roll': (-2.74385, 2.84121)}
JOINTS = [c[0] for c in CADENA]
GRIPPER_LIM = (-0.174533, 1.74533)
MONTAJE = np.array([-0.15, 0.0, 0.010 + 0.091])            # so101_base_link respecto de base_footprint (sin rotación)


def _rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]); Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]]); Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def _T(xyz, rpy):
    T = np.eye(4); T[:3, :3] = _rpy(*rpy); T[:3, 3] = xyz; return T


def _Rz(q):
    c, s = np.cos(q), np.sin(q); T = np.eye(4); T[0, 0], T[0, 1], T[1, 0], T[1, 1] = c, -s, s, c; return T


def fk_all(q):
    """Devuelve la lista de transformaciones (marco de cada articulación y de la herramienta) respecto de base_footprint."""
    T = np.eye(4); T[:3, 3] = MONTAJE; out = []
    for (n, xyz, rpy), qi in zip(CADENA, q):
        T = T @ _T(xyz, rpy) @ _Rz(qi); out.append(T.copy())
    out.append(T @ _T(*TOOL))
    return out


def fk(q):
    """(posición de la punta de la pinza, eje de aproximación unitario) en base_footprint. El eje apunta de la muñeca a la punta."""
    Ts = fk_all(q)
    p = Ts[-1][:3, 3]; muneca = Ts[4][:3, 3]
    a = p - muneca; a /= np.linalg.norm(a)
    return p, a


def elevacion_deg(a):
    """Ángulo del eje de aproximación respecto de la horizontal (positivo = apunta hacia abajo)."""
    return float(np.degrees(np.arcsin(-a[2])))


def ik(p_obj, inclinacion_deg, q0=None, roll=0.0, intentos=40, seed=0):
    """Busca q (5 articulaciones) para que la punta llegue a p_obj (base_footprint) con el eje de aproximación inclinado `inclinacion_deg` hacia abajo
    y apuntando al acimut del objetivo. Devuelve (q, error_pos_m, error_incl_deg) o None."""
    rng = np.random.default_rng(seed)
    lo = np.array([LIMITES[n][0] for n in JOINTS]); hi = np.array([LIMITES[n][1] for n in JOINTS])
    az = np.arctan2(p_obj[1] - MONTAJE[1], p_obj[0] - MONTAJE[0])
    objetivo_a = np.array([np.cos(az) * np.cos(np.radians(inclinacion_deg)), np.sin(az) * np.cos(np.radians(inclinacion_deg)), -np.sin(np.radians(inclinacion_deg))])
    mejor = None
    for k in range(intentos):
        q = (np.array(q0, float) if (q0 is not None and k == 0) else rng.uniform(lo, hi))
        q[0] = np.clip(az, lo[0], hi[0]); q[4] = roll
        for it in range(120):
            p, a = fk(q); e = np.concatenate([p_obj - p, 0.05 * (objetivo_a - a)])
            if np.linalg.norm(e[:3]) < 2e-4 and np.linalg.norm(e[3:]) < 1e-3:
                break
            J = np.zeros((6, 5)); h = 1e-5
            for j in range(4):                       # el giro de muñeca (índice 4) se fija a `roll`
                dq = q.copy(); dq[j] += h; p2, a2 = fk(dq)
                J[:3, j] = (p2 - p) / h; J[3:, j] = 0.05 * (a2 - a) / h
            Jr = J[:, :4]
            dq = np.linalg.solve(Jr.T @ Jr + 1e-4 * np.eye(4), Jr.T @ e)
            q[:4] = np.clip(q[:4] + dq, lo[:4], hi[:4])
        p, a = fk(q); ep = float(np.linalg.norm(p_obj - p)); ei = abs(elevacion_deg(a) - inclinacion_deg)
        cand = (q.copy(), ep, ei)
        if mejor is None or ep + 0.002 * ei < mejor[1] + 0.002 * mejor[2]:
            mejor = cand
        if ep < 1e-3 and ei < 1.0:
            break
    return mejor


JAW_C = np.array([0.0202, 0.0188, -0.0234])        # eje de la mordaza móvil en gripper_link (URDF: joint "gripper", eje -y)
JAW_AX = np.array([0.0, -1.0, 0.0])
TCP_L = np.array(TOOL[0])


def _rodrigues(ax, t):
    ax = ax / np.linalg.norm(ax); K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K


def jaw_gap_vector(q, g):
    """Vector (en base_footprint) de la punta de la mordaza fija (TCP) a la almohadilla de la mordaza móvil abierta un ángulo g. Con wrist_roll = ±pi/2 es horizontal."""
    Rg = fk_all(q)[4][:3, :3]
    p = JAW_C + _rodrigues(JAW_AX, g) @ (TCP_L - JAW_C)
    return Rg @ (p - TCP_L)


if __name__ == '__main__':
    q0 = np.zeros(5); p, a = fk(q0)
    print('FK en cero: punta', np.round(p, 4), 'eje', np.round(a, 3), 'elevación', round(elevacion_deg(a), 1), '°')
