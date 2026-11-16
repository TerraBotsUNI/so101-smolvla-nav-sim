# Análisis por posición del cubo pedido en la fila (izquierda / centro / derecha).
# Replica el cálculo del diagnóstico del 15-nov (analisis5.py + comun.py): giro de muñeca en el
# primer cierre = grados(wrist_roll medido - pi/2); centro de agarre por FK inversa de la fórmula
# del experto; tipo de fallo por la meseta de la pinza. Solo lee archivos ya existentes.
# Uso: python analisis_derecha.py <raiz_datos> <carpeta_salida>
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from comun import metricas, parse_cubos, J6

R, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
POS = {0: 'izquierda', 1: 'centro', 2: 'derecha'}


def tipo(r):
    if r['exito']: return 'exito'
    if r.get('i_cierre', -1) < 0: return 'nunca_cierra'
    if r['n_cambios'] > 2: return 'oscila'
    if r['g_meseta'] < 0.1: return 'cierra_en_vacio'
    if np.isnan(r.get('espera_cierre_levanta', np.nan)): return 'sujeta_no_levanta'
    return 'sujeta_y_pierde'


def intento(d, cubo=None):
    m = json.load(open(os.path.join(d, 'meta.json')))
    a = pd.read_csv(os.path.join(d, 'acciones.csv'))
    if len(a) < 20: return None
    r, _ = metricas(a[['est_' + x for x in J6]].values, a.t_sim.values, a.acc_gripper.values, cubo)
    r.update(exito=int(bool(m['exito'])), color=m['color'], carpeta=os.path.basename(d))
    r['tipo'] = tipo(r)
    r['droll'] = float(np.degrees(r['roll'] - 1.5708)) if 'roll' in r else np.nan
    return r


filas = []
# ---------------- 1) misiones (navegación + recogida), alineando intentos con su misión
TANDAS = {'40k': 'final_vla40k_A7e2_s{s}', 'pinza=orden': 'final_vlapo40k_A7e2_s{s}', 'v2': 'final_vlav2_s{s}'}
CSV = {'40k': 'final_misiones_vla40k_A7e2_n20_s{s}.csv', 'pinza=orden': 'final_misiones_vlapo40k_A7e2_n20_s{s}.csv',
       'v2': 'final_misiones_vlav2_A7e2_n20_s{s}.csv'}
alineacion = []
for pol in TANDAS:
    for s in (21, 22, 23, 24):
        cdir = os.path.join(R, 'intentos_mision', TANDAS[pol].format(s=s))
        ccsv = os.path.join(R, 'registros', CSV[pol].format(s=s))
        if not os.path.exists(ccsv): continue
        M = pd.read_csv(ccsv)
        dirs = sorted(glob.glob(os.path.join(cdir, 'vla_*')), key=lambda d: os.path.getmtime(os.path.join(d, 'meta.json')))
        lleg = M[M.acercar_ok == 1]
        esper = int(lleg.pick_intentos.fillna(0).sum())
        ok_al = len(dirs) == esper
        if ok_al:
            k = 0
            for _, row in lleg.iterrows():
                pos = row.orden_cubos.split('-').index(row.color)
                for j in range(int(row.pick_intentos)):
                    d = dirs[k]; k += 1
                    if json.load(open(os.path.join(d, 'meta.json')))['color'] != row.color:
                        ok_al = False
                    r = intento(d)
                    if r is None: continue
                    r.update(fuente='mision', politica=pol, semilla=s, mision=int(row.mision), pos=pos, posicion=POS[pos], n_intento=j + 1,
                             pick_ok_mision=int(row.pick_ok))
                    filas.append(r)
        alineacion.append(dict(politica=pol, semilla=s, misiones=len(M), llegan_recoger=len(lleg), intentos_esperados=esper,
                               carpetas=len(dirs), alineado=int(ok_al)))
        if not ok_al:  # descartar lo añadido de esta tanda si los colores no cuadran
            filas = [f for f in filas if not (f['fuente'] == 'mision' and f['politica'] == pol and f['semilla'] == s)]
pd.DataFrame(alineacion).to_csv(os.path.join(OUT, 'alineacion_misiones.csv'), index=False)

# ---------------- 2) banco s910 (disposición de misión) y s900 (disposición de las demos): pose del cubo conocida
BANCO = {('40k', 's910'): ('eval_40k_mision_s910', 'eval_brazo_40k_mision_s910.csv'),
         ('ACT', 's910'): ('eval_act_mision_s910', 'eval_brazo_act_mision_s910.csv'),
         ('v2', 's910'): ('eval_v2_mision_s910', 'eval_brazo_v2_mision_s910.csv')}
EXPERTO = {}
for (pol, sem), (cdir, ccsv) in BANCO.items():
    E0 = pd.read_csv(os.path.join(R, 'registros', ccsv))
    for _, row in E0[E0.estrategia != 'vla'].iterrows():  # el experto (ik_directa) corrido en la misma tanda: solo resultado
        cub = parse_cubos(row.cubos); cy = cub[row.color][1]; otros = [v[1] for c, v in cub.items() if c != row.color]
        pos = 2 if all(o > cy for o in otros) else (0 if all(o < cy for o in otros) else 1)
        EXPERTO.setdefault((pol, sem, POS[pos]), []).append(int(row.exito))
    E = E0[E0.estrategia == 'vla'].reset_index(drop=True)
    dirs = sorted(glob.glob(os.path.join(R, 'intentos_vla_escena', cdir, 'vla_*')), key=lambda d: os.path.getmtime(os.path.join(d, 'meta.json')))
    assert len(dirs) == len(E), (pol, len(dirs), len(E))
    for (_, row), d in zip(E.iterrows(), dirs):
        cub = parse_cubos(row.cubos); cx, cy, cyaw = cub[row.color]
        assert json.load(open(os.path.join(d, 'meta.json')))['color'] == row.color
        otros = [v[1] for c, v in cub.items() if c != row.color]
        # y positiva = izquierda del robot (REP-103)
        pos = 2 if all(o > cy for o in otros) else (0 if all(o < cy for o in otros) else 1)
        r = intento(d, (cx, cy, cyaw))
        if r is None: continue
        r.update(fuente='banco_' + sem, politica=pol, semilla=int(row.semilla), mision=int(row.escena), pos=pos, posicion=POS[pos],
                 n_intento=1, cubo_x=cx, cubo_y=cy, cubo_yaw=cyaw)
        filas.append(r)

F = pd.DataFrame(filas)
# referencia del experto: relación giro de muñeca - yaw del cubo en sus demostraciones exitosas (10 N·m, centro)
D = pd.read_csv(os.path.join(R, 'demos_metricas.csv'))
D = D[(D.exito == 1) & (D.err_xy < 0.015)].copy(); D['droll'] = np.degrees(D.roll - 1.5708)
b = np.polyfit(D.cyaw, D.droll, 1)
F['droll_experto_ref'] = np.where(F.get('cubo_yaw').notna(), np.polyval(b, F.cubo_yaw), np.nan) if 'cubo_yaw' in F else np.nan
F['err_giro'] = F.droll - F.droll_experto_ref
# comun.centro_agarre usa el margen 18 mm de la primera ronda; v2 se grabó con 26 mm: su agarre nominal queda 8 mm hacia -u.
# err_u_nominal = error lateral respecto al agarre nominal de la receta con que se entrenó cada política
MARGEN_POL = {'40k': 0.018, 'pinza=orden': 0.018, 'ACT': 0.018, 'v2': 0.026}
F['err_u_nominal'] = F.err_u + F.politica.map(MARGEN_POL) - 0.018
cols = ['fuente', 'politica', 'semilla', 'mision', 'n_intento', 'pos', 'posicion', 'color', 'exito', 'tipo', 'droll', 'droll_experto_ref',
        'err_giro', 'err_u_nominal', 'ag_x', 'ag_y', 'err_x', 'err_y', 'err_u', 'err_n', 'err_yaw', 'cubo_x', 'cubo_y', 'cubo_yaw', 'g_meseta', 't_cierre', 'carpeta']
F = F[[c for c in cols if c in F.columns]]
F.to_csv(os.path.join(OUT, 'intentos_por_posicion.csv'), index=False, float_format='%.5g')

# ---------------- resumen
def resumen(X):
    o = dict(n=len(X), exitos=int(X.exito.sum()),
             giro_media=X.droll.mean(), giro_de=X.droll.std(),
             ag_x_cm=100 * X.ag_x.mean(), ag_y_cm=100 * X.ag_y.mean())
    for c in ('droll_experto_ref', 'err_giro', 'err_u_nominal', 'err_u', 'err_n', 'err_x', 'err_y', 'cubo_yaw', 'cubo_y'):
        if c in X and X[c].notna().any():
            k = 1000 if c.startswith('err_') and c != 'err_giro' else 1
            o[c + ('_mm' if k == 1000 else '') + '_media'] = k * X[c].mean(); o[c + ('_mm' if k == 1000 else '') + '_de'] = k * X[c].std()
    for c in ('err_giro', 'err_u_nominal'):
        if c in X and X[c].notna().any():
            o[c + ('_mm' if c != 'err_giro' else '') + '_mediana'] = (1000 if c != 'err_giro' else 1) * X[c].median()
    t = X.tipo.value_counts().to_dict(); o['tipos'] = '; '.join(f'{a}={v}' for a, v in t.items())
    return pd.Series(o)

P1 = F[F.n_intento == 1]
S = pd.DataFrame([dict(fuente=k[0], politica=k[1], pos=k[2], posicion=k[3], **resumen(X).to_dict()) for k, X in P1.groupby(['fuente', 'politica', 'pos', 'posicion'])])
S.to_csv(os.path.join(OUT, 'resumen_por_posicion.csv'), index=False, float_format='%.3g')
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print(pd.DataFrame(alineacion).to_string())
print('ajuste experto (demos): droll = %.3f*yaw + %.2f' % tuple(b))
print(S.round(2).to_string())
for k, v in EXPERTO.items(): print('experto (ik_directa) en la tanda', k, f'{sum(v)}/{len(v)}')


# tasa de fallo frente al error lateral (banco s910, las tres políticas, primer y único intento)
B = F[F.fuente == 'banco_s910'].copy(); B['eu'] = 1000 * B.err_u_nominal
T = B.groupby(pd.cut(B.eu, [-200, -4, -1, 1, 3, 6, 20, 200]), observed=True).exito.agg(['size', 'sum']).reset_index()
T['eu'] = T.eu.astype(str); T.to_csv(os.path.join(OUT, 'exito_por_error_lateral_s910.csv'), index=False)
print(T.to_string())
