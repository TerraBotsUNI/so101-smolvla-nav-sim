"""Parche (14-nov): sujeción suave del cubo durante el transporte (misión, hold=True), en el experto y en el VLA.
La pinza es de control por POSICIÓN (max_effort se ignora): ordenar GRIP_CLOSE con el cubo entre las mordazas la deja empujando con el
límite del URDF (10 N·m) y Gazebo genera fuerzas de contacto espurias que desplazan y giran el robot con las ruedas quietas (problema 27).
Tras el agarre se ordena (posición medida - SO101_APRIETE rad), como un servo real con par limitado.
Uso: python3 parche_sujecion.py <dir scripts> <apriete por defecto>"""
import os, sys
d, ap = sys.argv[1], sys.argv[2]
f = os.path.join(d, 'so101_trial.py'); s = open(f, encoding='utf-8').read()
assert 'def sujetar_suave' not in s
a = 'def grasp_cycle(m, strat, row, q_obs, hold=False):\n'
b = f'''APRIETE = float(os.environ.get('SO101_APRIETE', '{ap}'))   # rad que se aprieta por debajo de la posición medida al transportar (0 = sin cambio)


def sujetar_suave(m):
    """Transporte: deja la pinza apretando solo APRIETE rad por debajo de donde la detiene el cubo (en vez de empujar hacia 0.0 con 10 N·m)."""
    p = m.js.get('gripper')
    if APRIETE <= 0 or p is None or p < 0.15:        # pinza cerrada del todo = no hay cubo
        return
    m.mark('sujecion_suave'); m.gripper(p - APRIETE, wait=1.0, tries=1)


''' + a
assert a in s; s = s.replace(a, b, 1)
a = "            m.mark('transporte'); m.move_q(qc, 3.0); m.spin_for(1.0)\n"
assert a in s; s = s.replace(a, a + "        sujetar_suave(m)\n", 1)
open(f, 'w', encoding='utf-8', newline='\n').write(s)

f = os.path.join(d, 'so101_vla.py'); s = open(f, encoding='utf-8').read()
a = '    if not (hold and ok):\n        m.gripper(T.GRIP_OPEN); m.move_q(q_obs, 2.5)\n'
assert a in s and 'sujetar_suave' not in s
s = s.replace(a, '    if hold and ok:\n        T.sujetar_suave(m)\n' + a, 1)
open(f, 'w', encoding='utf-8', newline='\n').write(s); print('ok sujecion', ap)
