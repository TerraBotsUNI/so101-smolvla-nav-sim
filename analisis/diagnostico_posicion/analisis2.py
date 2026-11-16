import sys, os, glob, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from scipy import stats
from comun import *
R = sys.argv[1]; OUT = sys.argv[2]
pd.set_option('display.width', 300); pd.set_option('display.max_rows', 700); pd.set_option('display.max_columns', 60)
REG = os.path.join(R, 'vla/registros')
arch = {'vla40k_2Nm': ('eval_brazo_A7e2_40k_n50_s900.csv', 'vla'), 'exp_2Nm': ('eval_brazo_A7e2_40k_n50_s900.csv', 'ik_directa'),
        'vlaPO_2Nm': ('eval_brazo_A7e2_po40k_n50_s900.csv', 'vla'),
        'vla40k_10Nm': ('eval_escena_40k_n50_2026-11-13.csv', 'vla'),
        'vla20k_10Nm': ('eval_escena_definitivo_n50_FINAL_2026-11-13.csv', 'vla'), 'exp_10Nm': ('eval_escena_definitivo_n50_FINAL_2026-11-13.csv', 'ik_directa'),
        'nacc10': ('eval_brazo_A7e2_40k_nacc10_n50_s900.csv', 'vla'), 'nacc15': ('eval_brazo_A7e2_40k_nacc15_n50_s900.csv', 'vla')}
T = None
for k, (f, est) in arch.items():
    p = os.path.join(REG, f)
    if not os.path.exists(p):
        continue
    d = pd.read_csv(p); d = d[d.estrategia == est].drop_duplicates('escena', keep='last').set_index('escena')
    if T is None:
        c = d.cubos.apply(parse_cubos)
        T = pd.DataFrame({'color': d.color, 'cubos': d.cubos})
        T['cx'] = [c[i][d.color[i]][0] for i in d.index]; T['cy'] = [c[i][d.color[i]][1] for i in d.index]; T['cyaw'] = [c[i][d.color[i]][2] for i in d.index]
        for lado, sg in (('izq', 1), ('der', -1)):
            dx, dy, yw = [], [], []
            for i in d.index:
                o = [v for kk, v in c[i].items() if kk != d.color[i] and sg * (v[1] - c[i][d.color[i]][1]) > 0][0]
                dx.append(o[0] - c[i][d.color[i]][0]); dy.append(abs(o[1] - c[i][d.color[i]][1])); yw.append(o[2])
            T[lado + '_dx'] = dx; T[lado + '_dy'] = dy; T[lado + '_yaw'] = yw
    else:
        assert (d.cubos.reindex(T.index).dropna() == T.cubos.reindex(d.index)).all(), k
    T[k] = d.exito
    T[k + '_msg'] = d.mensaje
T.to_csv(os.path.join(OUT, 'escenas_cruzadas.csv'))
runs = [k for k in arch if k in T.columns]
vla_full = [k for k in runs if k.startswith('vla') and T[k].notna().sum() == 50]
print('totales:', {k: (int(T[k].sum()), int(T[k].notna().sum())) for k in runs})
T['n_fallos_vla'] = (1 - T[vla_full]).sum(axis=1)
T['n_fallos_exp'] = (1 - T[[k for k in runs if k.startswith('exp')]]).sum(axis=1)
print(T[['color', 'cx', 'cy', 'cyaw', 'izq_dx', 'izq_dy', 'der_dx', 'der_dy'] + runs + ['n_fallos_vla', 'n_fallos_exp']].round(3).to_string())
print('mensajes experto:', pd.concat([T[k + '_msg'] for k in runs if k.startswith('exp')]).value_counts().to_dict())
print('distribucion n_fallos_vla (de %d corridas):' % len(vla_full), T.n_fallos_vla.value_counts().sort_index().to_dict())
# ¿fallos sistematicos por escena? comparar con binomial homogenea
p = 1 - T[vla_full].values.mean(); n = len(vla_full)
print('p fallo medio VLA', round(p, 3), 'esperado binomial:', {k: round(50 * stats.binom.pmf(k, n, p), 1) for k in range(n + 1)})
# varianza entre escenas: prueba de Cochran Q aproximada
X = 1 - T[vla_full].values
k = X.shape[1]; Cj = X.sum(0); Ri = X.sum(1); Nn = X.sum()
Q = (k - 1) * (k * (Cj ** 2).sum() - Nn ** 2) / (k * Nn - (Ri ** 2).sum())
print('Cochran Q entre corridas VLA =', round(Q, 2), 'p =', round(1 - stats.chi2.cdf(Q, k - 1), 3))
# simulacion: dispersión de fallos por escena frente a homogeneidad
rng = np.random.default_rng(0); obs = Ri.var(); sim = [rng.binomial(n, p, 50).var() for _ in range(20000)]
print('var(n fallos por escena) obs =', round(obs, 3), 'p(sim >= obs) =', np.mean(np.array(sim) >= obs))
# por factores
T['absyaw'] = T.cyaw.abs()
def tabla(col, bins, lab=None):
    T['_b'] = pd.cut(T[col], bins)
    g = T.groupby('_b', observed=True)
    out = pd.DataFrame({'n_esc': g.size()})
    for kk in vla_full + [r for r in runs if r.startswith('exp')]:
        out[kk] = g[kk].sum().astype(int)
    out['VLA_pool'] = [f"{int(T.loc[T._b == b, vla_full].values.sum())}/{int((T._b == b).sum() * len(vla_full))}" for b in out.index]
    out['VLA_%'] = [round(100 * T.loc[T._b == b, vla_full].values.mean(), 0) for b in out.index]
    ex = [r for r in runs if r.startswith('exp')]
    out['EXP_%'] = [round(100 * T.loc[T._b == b, ex].values.mean(), 0) for b in out.index]
    print('\n== por', col); print(out.to_string())
tabla('cyaw', [-41, -30, -20, -10, 0, 10, 20, 30, 41])
tabla('absyaw', [-1, 10, 20, 30, 35, 41])
tabla('cx', [0.139, 0.15, 0.16, 0.17, 0.181])
tabla('cy', [-0.026, -0.0125, 0, 0.0125, 0.026])
T['min_dy'] = T[['izq_dy', 'der_dy']].min(axis=1); tabla('min_dy', [0.124, 0.13, 0.135, 0.14, 0.146])
g = T.groupby('color'); print('\n== por color'); print(pd.DataFrame({'n': g.size(), **{k: g[k].sum() for k in runs}, 'VLA_%': g[vla_full].mean().mean(axis=1).round(2)}).to_string())
# regresion logistica simple (pool VLA) con |yaw|
try:
    import statsmodels.api as sm
    L = T[vla_full].stack().reset_index(); L.columns = ['escena', 'corrida', 'exito']
    L = L.join(T[['cx', 'cy', 'cyaw', 'absyaw', 'min_dy']], on='escena')
    Xm = sm.add_constant(pd.DataFrame({'absyaw10': L.absyaw / 10, 'yaw_neg': (L.cyaw < 0).astype(float), 'cx_cm': (L.cx - 0.16) * 100, 'cy_cm': L.cy * 100, 'min_dy_cm': (L.min_dy - 0.135) * 100}))
    mod = sm.GEE(L.exito, Xm, groups=L.escena, family=sm.families.Binomial()).fit()
    print(mod.summary().tables[1])
except Exception as e:
    print('sin statsmodels:', e)
# Fisher |yaw|>=35 frente al resto, por corrida y agrupado
for kk in vla_full + [r for r in runs if r.startswith('exp')]:
    a = T[T.absyaw >= 35][kk]; b = T[T.absyaw < 35][kk]
    print(kk, f'|yaw|>=35: {int(a.sum())}/{len(a)}  resto: {int(b.sum())}/{len(b)}  Fisher p={stats.fisher_exact([[a.sum(), len(a) - a.sum()], [b.sum(), len(b) - b.sum()]])[1]:.4f}')
