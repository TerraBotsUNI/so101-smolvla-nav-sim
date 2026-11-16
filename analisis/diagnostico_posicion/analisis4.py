import sys, os, glob, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from scipy import stats
from comun import *
R = sys.argv[1]; R2 = sys.argv[2]; OUT = sys.argv[3]
pd.set_option('display.width', 300); pd.set_option('display.max_rows', 700); pd.set_option('display.max_columns', 60)
# ---------- 1) misiones: intentos de recogida
print('== MISIONES (A7e2): intentos de RECOGER')
for pref in ('experto', 'vla40k', 'vlapo40k'):
    L = []
    for f in sorted(glob.glob(os.path.join(R2, 'vla/registros', f'final_misiones_{pref}_A7e2_n20_s*.csv'))):
        d = pd.read_csv(f); d['sem'] = f[-6:-4]; L.append(d)
    M = pd.concat(L, ignore_index=True); lleg = M[M.acercar_ok == 1]
    print(f'{pref}: misiones {len(M)}, exito {int(M.exito.sum())}; llegan a RECOGER {len(lleg)}; pick_ok {int(lleg.pick_ok.sum())}')
    print('   pick_intentos x pick_ok:', pd.crosstab(lleg.pick_intentos, lleg.pick_ok).to_dict())
    print('   etapa_fallo:', M.etapa_fallo.fillna('').value_counts().to_dict())
    print('   mensajes de pick fallido:', lleg[lleg.pick_ok == 0].pick_msg.value_counts().to_dict())
# ---------- 2) evaluaciones a 10 N·m (13-nov): mismas metricas
print('\n== VLA a 10 N·m (13-nov) frente a 2 N·m (14-nov): dinamica de la pinza y espera')
def cargar(csvp, carp, nom):
    df = pd.read_csv(csvp); v = df[df.estrategia == 'vla'].drop_duplicates('escena', keep='last').reset_index(drop=True)
    dirs = [d for d in sorted(glob.glob(os.path.join(carp, 'vla_*'))) if os.path.exists(os.path.join(d, 'meta.json')) and os.path.exists(os.path.join(d, 'acciones.csv'))]
    metas = [json.load(open(os.path.join(d, 'meta.json'))) for d in dirs]
    j = 0; filas = []
    for i, row in v.iterrows():
        k = j
        while k < len(dirs):
            m = metas[k]
            if m['color'] == row.color and abs((m.get('z_cubo') or 0.0) - row.cubo_z) < 0.003:
                a = pd.read_csv(os.path.join(dirs[k], 'acciones.csv')); cub = parse_cubos(row.cubos)
                r, _ = metricas(a[['est_' + x for x in J6]].values, a.t_sim.values, a.acc_gripper.values, cub[row.color])
                r.update(corrida=nom, escena=int(row.escena), exito=int(row.exito), cyaw=cub[row.color][2], carpeta=os.path.basename(dirs[k]))
                # serie de la pinza tras el cierre
                g = a.est_gripper.values; i0 = r.get('i_cierre', -1)
                if i0 >= 0:
                    for dt_ in (5, 10, 20, 30):
                        r[f'g_{dt_}'] = float(g[min(len(g) - 1, i0 + dt_)])
                filas.append(r); j = k + 1; break
            k += 1
    print(nom, 'emparejadas', len(filas), 'de', len(v), 'carpetas', len(dirs))
    return pd.DataFrame(filas)
A = cargar(os.path.join(R, 'vla/registros/eval_escena_40k_n50_2026-11-13.csv'), os.path.join(R2, 'vla/intentos_vla_escena/modelo_40k'), '40k_10Nm')
B = cargar(os.path.join(R, 'vla/registros/eval_brazo_A7e2_40k_n50_s900.csv'), os.path.join(R, 'vla/intentos_vla_escena/eval_A7e2_40k'), '40k_2Nm')
C = cargar(os.path.join(R, 'vla/registros/eval_brazo_A7e2_po40k_n50_s900.csv'), os.path.join(R, 'vla/intentos_vla_escena/eval_A7e2_po40k'), 'po40k_2Nm')
extra = []
for nn in ('nacc10', 'nacc15'):
    p = os.path.join(R, f'vla/registros/eval_brazo_A7e2_40k_{nn}_n50_s900.csv')
    if os.path.exists(p):
        extra.append(cargar(p, os.path.join(R, f'vla/intentos_vla_escena/eval_A7e2_40k_{nn}'), nn))
def tipo(r):
    if r.exito: return 'exito'
    if r.i_cierre < 0: return 'nunca_cierra'
    if r.n_cambios > 2: return 'oscila'
    if r.g_meseta < 0.1: return 'cierra_en_vacio'
    if np.isnan(r.espera_cierre_levanta): return 'sujeta_no_levanta'
    return 'sujeta_y_pierde'
ALL = pd.concat([A, B, C] + extra, ignore_index=True); ALL['tipo'] = ALL.apply(tipo, axis=1)
print(pd.crosstab(ALL.corrida, ALL.tipo, margins=True).to_string())
for nom, X in ALL.groupby('corrida'):
    ok = X[X.exito == 1]
    print(f'{nom}: exitos n={len(ok)} | pinza tras cierre +0.5s/+1s/+2s/+3s medianas = {ok.g_5.median():.3f}/{ok.g_10.median():.3f}/{ok.g_20.median():.3f}/{ok.g_30.median():.3f} | g_fin {ok.g_fin.median():.3f} | espera cierre->levanta p10/p50/p90/max = {ok.espera_cierre_levanta.quantile(.1):.1f}/{ok.espera_cierre_levanta.median():.1f}/{ok.espera_cierre_levanta.quantile(.9):.1f}/{ok.espera_cierre_levanta.max():.1f} | t_cierre p50 {ok.t_cierre.median():.1f} | tcp_z mm {1000 * X.tcp_z.median():.1f} | err_u mm media {1000 * X.err_u.mean():.2f} sd {1000 * X.err_u.std():.2f} | |err_yaw| p50 {X.err_yaw.abs().median():.1f} p90 {X.err_yaw.abs().quantile(.9):.1f}')
ALL.to_csv(os.path.join(OUT, 'vla_todas_corridas_metricas.csv'), index=False)
print('\nexito por err_u (mm), todas las corridas VLA:'); print(ALL.groupby(pd.cut(1000 * ALL.err_u, [-9, -1, 1, 2, 3, 4, 9]), observed=True).exito.agg(['size', 'sum', 'mean']).round(2).to_string())
print('exito por err_u con yaw>=-25:'); Y = ALL[ALL.cyaw >= -25]; print(Y.groupby(pd.cut(1000 * Y.err_u, [-9, -1, 1, 2, 3, 4, 9]), observed=True).exito.agg(['size', 'sum', 'mean']).round(2).to_string())
print('exito por err_u con yaw<-25:'); Y = ALL[ALL.cyaw < -25]; print(Y.groupby(pd.cut(1000 * Y.err_u, [-9, -1, 1, 2, 3, 4, 9]), observed=True).exito.agg(['size', 'sum', 'mean']).round(2).to_string())
# repetibilidad del error por escena entre corridas (¿sesgo sistematico por escena o ruido?)
P = ALL[ALL.corrida.isin(['40k_10Nm', '40k_2Nm', 'po40k_2Nm'])].pivot_table(index='escena', columns='corrida', values='err_u')
print('\ncorrelacion de err_u por escena entre corridas:'); print(P.corr().round(2).to_string())
P2 = ALL[ALL.corrida.isin(['40k_10Nm', '40k_2Nm', 'po40k_2Nm'])].pivot_table(index='escena', columns='corrida', values='err_yaw')
print('correlacion de err_yaw por escena entre corridas:'); print(P2.corr().round(2).to_string())
# sesgos sistematicos del VLA: err_u ~ cx, cy, cyaw
import statsmodels.api as sm
S = ALL[ALL.corrida.isin(['40k_10Nm', '40k_2Nm', 'po40k_2Nm'])].dropna(subset=['err_u']).copy()
esc = pd.read_csv(os.path.join(OUT, 'escenas_cruzadas.csv')).set_index('escena')
S = S.join(esc[['cx', 'cy']], on='escena')
for dep in ('err_u', 'err_x', 'err_y'):
    X = sm.add_constant(pd.DataFrame({'cx_cm': (S.cx - 0.16) * 100, 'cy_cm': S.cy * 100, 'yaw10': S.cyaw / 10}))
    m = sm.OLS(1000 * S[dep], X).fit(); print(f'{dep} (mm) ~', {k: f'{v:.2f} (p={m.pvalues[k]:.3f})' for k, v in m.params.items()}, 'R2', round(m.rsquared, 2), 'sd resid', round(np.sqrt(m.scale), 2))
# mismo modelo, misma escena: repetibilidad del resultado 40k (10 N·m) frente a 40k (2 N·m)
T = esc
print('\n40k 10Nm x 40k 2Nm:', pd.crosstab(T.vla40k_10Nm, T.vla40k_2Nm).to_dict())
print('40k 2Nm x po40k 2Nm:', pd.crosstab(T.vla40k_2Nm, T.vlaPO_2Nm).to_dict())
# tiempos del lazo de control
print('\n== tiempos del lazo (40k 2 N·m)')
V = pd.read_csv(os.path.join(OUT, 'intentos_vla_metricas.csv'))
for nom, X in V.groupby('corrida'):
    print(nom, 'pasos p50', X.pasos.median(), 'ms por paso p50', round(X.ms_med.median(), 1), 'inferencias (ms>150) p50', X.n_inf.median(), 'ms inferencia p50', round(X.ms_inf.median(), 1), 'dt_max p50', round(X.dt_max.median(), 2), 'pasos con dt>0.15', X.dt_grande.median(), 'dt<0.02', X.dt0.median())
