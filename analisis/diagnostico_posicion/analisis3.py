import sys, os, glob, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from scipy import stats
from comun import *
R = sys.argv[1]; OUT = sys.argv[2]
pd.set_option('display.width', 300); pd.set_option('display.max_rows', 700); pd.set_option('display.max_columns', 60)
D = pd.read_csv(os.path.join(OUT, 'demos_metricas.csv')); V = pd.read_csv(os.path.join(OUT, 'intentos_vla_metricas.csv'))
print('== DEMOS: episodios con metadatos incoherentes (|err_xy|>1.5 cm en el cierre)')
bad = D[(D.i_cierre >= 0) & (D.err_xy > 0.015)]
print(len(bad), 'episodios; por conjunto y rango de episodio:', bad.groupby('conj').epn.agg(['min', 'max', 'size']).to_dict())
print(bad[['conj', 'ep', 'exito', 'err_x', 'err_y', 'err_xy', 't_cierre']].round(3).head(60).to_string())
Dc = D[~D.index.isin(bad.index)].copy()
print('demos coherentes:', len(Dc), 'exito', Dc.exito.sum())
Dc['absyaw'] = Dc.cyaw.abs()
def tab(df, col, bins, nom):
    b = pd.cut(df[col], bins); g = df.groupby(b, observed=True).exito
    o = pd.DataFrame({'n': g.size(), 'ok': g.sum(), '%': (100 * g.mean()).round(0)}); print(f'\n-- {nom} por {col}'); print(o.to_string())
tab(Dc, 'cyaw', [-41, -35, -30, -25, -20, -10, 0, 10, 20, 25, 30, 35, 41], 'EXPERTO (demos, 10 N·m)')
tab(Dc, 'cx', [0.139, 0.15, 0.16, 0.17, 0.181], 'EXPERTO (demos)')
tab(Dc, 'cy', [-0.026, -0.0125, 0, 0.0125, 0.026], 'EXPERTO (demos)')
print('\nfallos del experto en demos: tipo por meseta de pinza')
f = Dc[(Dc.exito == 0) & (Dc.i_cierre >= 0)]
print('  cierra en vacio (g<0.1):', (f.g_meseta < 0.1).sum(), ' sujeta y lo pierde (g>=0.3):', (f.g_meseta >= 0.3).sum(), ' total', len(f))
print('  cierra en vacio por yaw:', pd.cut(f[f.g_meseta < 0.1].cyaw, [-41, -30, -10, 10, 30, 41]).value_counts().sort_index().to_dict())
print('  lo pierde por yaw      :', pd.cut(f[f.g_meseta >= 0.3].cyaw, [-41, -30, -10, 10, 30, 41]).value_counts().sort_index().to_dict())
ok = Dc[Dc.exito == 1]
print('\ncobertura de entrenamiento (demos exitosas) por yaw:', pd.cut(ok.cyaw, [-41, -30, -20, -10, 0, 10, 20, 30, 41]).value_counts().sort_index().to_dict())
print('demos exitosas: err_u mm  p5/p50/p95 =', (1000 * ok.err_u.quantile([.05, .5, .95])).round(2).tolist(), ' err_n mm', (1000 * ok.err_n.quantile([.05, .5, .95])).round(2).tolist(), ' err_yaw', ok.err_yaw.quantile([.05, .5, .95]).round(1).tolist())
print('demos exitosas: g_meseta p5/p50/p95', ok.g_meseta.quantile([.05, .5, .95]).round(3).tolist(), ' g_fin (tras levantar)', ok.g_fin.quantile([.05, .5, .95]).round(3).tolist())
print('demos exitosas: espera cierre->levanta s', ok.espera_cierre_levanta.quantile([.05, .5, .95]).round(2).tolist(), ' tcp_z cierre mm', (1000 * ok.tcp_z.quantile([.05, .5, .95])).round(1).tolist())
# roll usado por el experto frente al yaw (bimodalidad cerca de +-45)
ok2 = ok.copy(); ok2['droll'] = np.degrees(ok2.roll - 1.5708)
print('\nexperto: correccion de giro de muñeca (grados) por yaw del cubo')
print(ok2.groupby(pd.cut(ok2.cyaw, [-41, -35, -30, -20, -10, 0, 10, 20, 30, 35, 41]), observed=True).droll.agg(['size', 'mean', 'std', 'min', 'max']).round(1).to_string())

print('\n\n== VLA (2 N·m): 40k y po40k')
W = V[V.corrida.isin(['40k', 'po40k'])].copy()
W['absyaw'] = W.cyaw.abs(); W['droll'] = np.degrees(W.roll - 1.5708)
def tipo(r):
    if r.exito: return 'exito'
    if r.i_cierre < 0: return 'nunca_cierra'
    if r.n_cambios > 2: return 'oscila'
    if r.g_meseta < 0.1: return 'cierra_en_vacio'
    if np.isnan(r.espera_cierre_levanta): return 'sujeta_no_levanta'
    return 'sujeta_y_pierde'
W['tipo'] = W.apply(tipo, axis=1)
print(pd.crosstab(W.corrida, W.tipo, margins=True).to_string())
for c in ['err_u', 'err_n', 'err_x', 'err_y']:
    a = 1000 * W[W.exito == 1][c]; b = 1000 * W[W.tipo == 'cierra_en_vacio'][c]
    print(f'{c} mm: exito media={a.mean():.2f} sd={a.std():.2f} | cierra_en_vacio media={b.mean():.2f} sd={b.std():.2f} | Mann-Whitney p={stats.mannwhitneyu(a, b).pvalue:.4f}')
a = W[W.exito == 1].err_yaw.abs(); b = W[W.exito == 0].err_yaw.abs()
print(f'|err_yaw| grados: exito mediana={a.median():.1f} p90={a.quantile(.9):.1f} | fallo mediana={b.median():.1f} p90={b.quantile(.9):.1f} | MW p={stats.mannwhitneyu(a, b).pvalue:.4f}')
print('tcp_z cierre mm VLA p5/p50/p95:', (1000 * W.tcp_z.quantile([.05, .5, .95])).round(1).tolist(), ' vel_cierre rad/s p50:', round(W.vel_cierre.median(), 3))
print('espera cierre->levanta (s) VLA exito p5/p25/p50/p75/p95:', W[W.exito == 1].espera_cierre_levanta.quantile([.05, .25, .5, .75, .95]).round(1).tolist())
print('espera en cierra_en_vacio:', W[W.tipo == 'cierra_en_vacio'].espera_cierre_levanta.quantile([.05, .5, .95]).round(1).tolist())
print('\nexito VLA por err_u (mm):'); print(W.groupby(pd.cut(1000 * W.err_u, [-8, -1, 1, 2, 3, 4, 8]), observed=True).exito.agg(['size', 'sum', 'mean']).round(2).to_string())
print('exito VLA por |err_yaw|:'); print(W.groupby(pd.cut(W.err_yaw.abs(), [-1, 3, 6, 10, 15, 25, 46]), observed=True).exito.agg(['size', 'sum', 'mean']).round(2).to_string())
print('\nVLA: correccion de giro de muñeca (grados) frente al yaw del cubo (el experto usa droll ~ -yaw... ver signo en demos)')
print(W[['corrida', 'escena', 'cyaw', 'droll', 'err_yaw', 'err_u', 'exito', 'tipo']].sort_values('cyaw').round(1).to_string())
try:
    import statsmodels.api as sm
    X = sm.add_constant(pd.DataFrame({'err_u_mm': 1000 * W.err_u, 'abs_err_yaw10': W.err_yaw.abs() / 10, 'yaw_neg': (W.cyaw < 0).astype(float), 'tcp_z_mm': 1000 * W.tcp_z}))
    m = sm.Logit(W.exito, X).fit(disp=0); print(m.summary().tables[1])
except Exception as e:
    print('logit:', e)
W.to_csv(os.path.join(OUT, 'vla_2Nm_clasificado.csv'), index=False)
