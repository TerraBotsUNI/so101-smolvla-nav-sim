import sys, os, glob, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from comun import *
R = sys.argv[1]; OUT = sys.argv[2]
pd.set_option('display.width', 300); pd.set_option('display.max_rows', 700); pd.set_option('display.max_columns', 60)
filas = []
for sub in ('crudas_escena_a', 'crudas_escena_b'):
    for d in sorted(glob.glob(os.path.join(R, 'demos', sub, 'ep_*'))):
        mp = os.path.join(d, 'meta.json'); ep = os.path.join(d, 'estado.csv')
        if not (os.path.exists(mp) and os.path.exists(ep)):
            continue
        m = json.load(open(mp)); e = pd.read_csv(ep)
        if len(e) < 5:
            continue
        col = m['color']; cub = {c: (v[0], v[1], math.degrees(v[2])) for c, v in m['cubos'].items()}
        q6 = e[J6].values; t = e.t_sim.values
        r, tcp = metricas(q6, t, None, cub[col])
        otros = [c for c in cub if c != col]
        izq = [c for c in otros if cub[c][1] > cub[col][1]][0]; der = [c for c in otros if c != izq][0]
        dg = m.get('diagnostico', {})
        r.update(conj=sub[-1], ep=os.path.basename(d), color=col, exito=int(bool(m['exito'])), motivo=m.get('motivo', ''), instr=m['instruccion'],
                 cx=cub[col][0], cy=cub[col][1], cyaw=cub[col][2],
                 izq_dx=cub[izq][0] - cub[col][0], izq_dy=cub[izq][1] - cub[col][1], izq_yaw=cub[izq][2], izq_color=izq,
                 der_dx=cub[der][0] - cub[col][0], der_dy=cub[der][1] - cub[col][1], der_yaw=cub[der][2], der_color=der,
                 err_est1=dg.get('err_est1_mm'), phi_ag=dg.get('phi_agarre'), z_cubo_final=dg.get('z_cubo_final'), epn=int(os.path.basename(d)[3:]))
        filas.append(r)
D = pd.DataFrame(filas); D.to_csv(os.path.join(OUT, 'demos_metricas.csv'), index=False)
print('episodios', len(D), 'exitosos', D.exito.sum())
print(D.groupby(['conj', 'exito']).size())
print(D[D.exito == 0].motivo.str.replace(r'\(.*\)', '', regex=True).value_counts())
ok = D[D.exito == 1]
for c in ['pasos', 't_cierre', 'g_meseta', 'g_min', 'g_fin', 'tcp_z', 'err_x', 'err_y', 'err_u', 'err_n', 'err_yaw', 'phi', 'espera_cierre_levanta', 'z_max_tras', 'vel_cierre', 'cx', 'cy', 'cyaw']:
    v = ok[c].dropna(); print(f'{c:24s} n={len(v)} media={v.mean():.4f} sd={v.std():.4f} p1={v.quantile(.01):.4f} p5={v.quantile(.05):.4f} p50={v.median():.4f} p95={v.quantile(.95):.4f} p99={v.quantile(.99):.4f}')
print('--- fallidos con cierre (no levanto)')
fl = D[(D.exito == 0) & (D.i_cierre >= 0)]
print(fl[['ep', 'conj', 'color', 'motivo', 'cx', 'cy', 'cyaw', 'g_meseta', 'g_fin', 'err_u', 'err_n', 'err_yaw', 'espera_cierre_levanta', 'z_max_tras', 'err_est1']].round(3).to_string())
# evolucion temporal: tasa de exito por bloques de episodios (antes/despues de las correcciones de las 15:59)
D['bloque'] = (D.epn // 50)
print(D.groupby(['conj', 'bloque']).exito.agg(['mean', 'size']))
