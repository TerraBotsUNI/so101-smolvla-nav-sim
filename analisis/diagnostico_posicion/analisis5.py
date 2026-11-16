import sys, os, glob, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from scipy import stats
from comun import *
R3 = sys.argv[1]; OUT = sys.argv[2]
pd.set_option('display.width', 300); pd.set_option('display.max_rows', 700); pd.set_option('display.max_columns', 60)
filas = []
for d in sorted(glob.glob(os.path.join(R3, 'vla/intentos_mision/final_vla*A7e2*/vla_*'))):
    mp, ap = os.path.join(d, 'meta.json'), os.path.join(d, 'acciones.csv')
    if not (os.path.exists(mp) and os.path.exists(ap)):
        continue
    m = json.load(open(mp)); a = pd.read_csv(ap)
    if len(a) < 20:
        continue
    r, _ = metricas(a[['est_' + x for x in J6]].values, a.t_sim.values, a.acc_gripper.values, None)
    r.update(tanda=os.path.basename(os.path.dirname(d)), carpeta=os.path.basename(d), exito=int(bool(m['exito'])), color=m['color'], z=m.get('z_cubo'))
    filas.append(r)
M = pd.DataFrame(filas)
def tipo(r):
    if r.exito: return 'exito'
    if r.i_cierre < 0: return 'nunca_cierra'
    if r.n_cambios > 2: return 'oscila'
    if r.g_meseta < 0.1: return 'cierra_en_vacio'
    if np.isnan(r.espera_cierre_levanta): return 'sujeta_no_levanta'
    return 'sujeta_y_pierde'
M['tipo'] = M.apply(tipo, axis=1); M['droll'] = np.degrees(M.roll - 1.5708)
M['modelo'] = np.where(M.tanda.str.contains('vlapo'), 'po40k', '40k')
print('intentos VLA en misiones (A7e2):', len(M), 'exitos', M.exito.sum())
print(pd.crosstab(M.modelo, M.tipo, margins=True).to_string())
# distribucion de donde cierra (aprox. posicion del cubo respecto al robot) y giro de muñeca: mision frente a banco
B = pd.read_csv(os.path.join(OUT, 'vla_todas_corridas_metricas.csv')); B = B[B.corrida.isin(['40k_2Nm', 'po40k_2Nm'])].copy(); B['droll'] = np.degrees(B.roll - 1.5708)
D = pd.read_csv(os.path.join(OUT, 'demos_metricas.csv')); D = D[(D.exito == 1) & (D.err_xy < 0.015)].copy(); D['droll'] = np.degrees(D.roll - 1.5708)
for nom, X in (('demos exitosas', D), ('banco VLA', B), ('mision VLA', M[M.i_cierre >= 0])):
    print(f'\n{nom} (n={len(X)}): centro de agarre x cm p1/p5/p50/p95/p99 = {(100 * X.ag_x.quantile([.01, .05, .5, .95, .99])).round(1).tolist()} | y cm = {(100 * X.ag_y.quantile([.01, .05, .5, .95, .99])).round(1).tolist()} | giro muñeca (grados) = {X.droll.quantile([.01, .05, .5, .95, .99]).round(0).tolist()}')
Mi = M[M.i_cierre >= 0].copy()
Mi['fuera_xy'] = (Mi.ag_x < 0.138) | (Mi.ag_x > 0.182) | (Mi.ag_y.abs() > 0.027)
print('\nmision: intentos con centro de agarre fuera del rango de las demos (x 14-18 cm, |y|<=2.5 cm, +2 mm):', int(Mi.fuera_xy.sum()), 'de', len(Mi))
print(pd.crosstab(Mi.fuera_xy, Mi.exito, margins=True).to_string())
print('\nmision: exito por |giro de muñeca| (aprox. |yaw| del cubo respecto al robot):')
print(Mi.groupby(pd.cut(Mi.droll, [-60, -25, -10, 0, 10, 25, 60]), observed=True).exito.agg(['size', 'sum', 'mean']).round(2).to_string())
print('mision: exito por y del agarre (cm):')
print(Mi.groupby(pd.cut(100 * Mi.ag_y, [-9, -2.5, -1.25, 0, 1.25, 2.5, 9]), observed=True).exito.agg(['size', 'sum', 'mean']).round(2).to_string())
print('mision: exito por x del agarre (cm):')
print(Mi.groupby(pd.cut(100 * Mi.ag_x, [10, 14, 15, 16, 17, 18, 25]), observed=True).exito.agg(['size', 'sum', 'mean']).round(2).to_string())
print('banco: exito por y del cubo... (ver analisis2)')
print('mision: espera cierre->levanta en exitos p10/p50/p90:', M[M.exito == 1].espera_cierre_levanta.quantile([.1, .5, .9]).round(1).tolist())
M.to_csv(os.path.join(OUT, 'vla_mision_metricas.csv'), index=False)
