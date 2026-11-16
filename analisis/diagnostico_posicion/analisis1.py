import sys, os, glob, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from comun import *
R = sys.argv[1]; OUT = sys.argv[2]
pd.set_option('display.width', 300); pd.set_option('display.max_rows', 700); pd.set_option('display.max_columns', 60)
REG = os.path.join(R, 'vla/registros')
corridas = {'40k': ('eval_brazo_A7e2_40k_n50_s900.csv', 'eval_A7e2_40k'), 'po40k': ('eval_brazo_A7e2_po40k_n50_s900.csv', 'eval_A7e2_po40k'),
            'nacc10': ('eval_brazo_A7e2_40k_nacc10_n50_s900.csv', 'eval_A7e2_40k_nacc10'), 'nacc15': ('eval_brazo_A7e2_40k_nacc15_n50_s900.csv', 'eval_A7e2_40k_nacc15')}
filas = []
for nom, (csvf, carp) in corridas.items():
    if not os.path.exists(os.path.join(REG, csvf)):
        continue
    df = pd.read_csv(os.path.join(REG, csvf)); v = df[df.estrategia == 'vla'].reset_index(drop=True)
    dirs = [d for d in sorted(glob.glob(os.path.join(R, 'vla/intentos_vla_escena', carp, 'vla_*'))) if os.path.exists(os.path.join(d, 'meta.json'))]
    metas = [json.load(open(os.path.join(d, 'meta.json'))) for d in dirs]
    # emparejar en orden: color igual y z del cubo igual (tolerancia 3 mm); las carpetas sobrantes (reintentos tras relanzar) se saltan
    j = 0; emp = []
    for i, row in v.iterrows():
        k = j
        while k < len(dirs):
            m = metas[k]
            if m['color'] == row.color and abs((m.get('z_cubo') or 0.0) - row.cubo_z) < 0.003:
                emp.append((i, dirs[k])); j = k + 1; break
            k += 1
    print(nom, 'filas vla', len(v), 'carpetas', len(dirs), 'emparejadas', len(emp), 'exitos', int(v.exito.sum()))
    for i, d in emp:
        row = v.loc[i]; cub = parse_cubos(row.cubos); m = json.load(open(os.path.join(d, 'meta.json')))
        a = pd.read_csv(os.path.join(d, 'acciones.csv'))
        q6 = a[['est_' + j_ for j_ in J6]].values; t = a.t_sim.values
        r, tcp = metricas(q6, t, a.acc_gripper.values, cub[row.color])
        otros = [c for c in cub if c != row.color]
        izq = [c for c in otros if cub[c][1] > cub[row.color][1]][0]; der = [c for c in otros if c != izq][0]
        ms = a.ms.values
        r.update(corrida=nom, escena=int(row.escena), color=row.color, exito=int(row.exito), cubo_z=row.cubo_z, carpeta=os.path.basename(d),
                 cx=cub[row.color][0], cy=cub[row.color][1], cyaw=cub[row.color][2],
                 izq_dx=cub[izq][0] - cub[row.color][0], izq_dy=cub[izq][1] - cub[row.color][1], izq_yaw=cub[izq][2], izq_color=izq,
                 der_dx=cub[der][0] - cub[row.color][0], der_dy=cub[der][1] - cub[row.color][1], der_yaw=cub[der][2], der_color=der,
                 ms_med=float(np.median(ms)), n_inf=int((ms > 150).sum()), ms_inf=float(np.median(ms[ms > 150])) if (ms > 150).any() else float('nan'),
                 dt0=int((np.diff(t) < 0.02).sum()), dt_grande=int((np.diff(t) > 0.15).sum()), dt_max=float(np.diff(t).max()))
        filas.append(r)
D = pd.DataFrame(filas); D.to_csv(os.path.join(OUT, 'intentos_vla_metricas.csv'), index=False)
cols = ['corrida', 'escena', 'color', 'exito', 'cubo_z', 'cx', 'cy', 'cyaw', 'pasos', 'n_cambios', 't_cierre', 'g_meseta', 'g_fin', 'tcp_z', 'err_x', 'err_y', 'err_u', 'err_n', 'err_yaw', 'phi', 'vel_cierre', 'espera_cierre_levanta', 'z_max_tras', 'z_fin', 'n_inf', 'ms_inf']
print(D[cols].round(3).to_string())
