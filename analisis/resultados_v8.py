#!/usr/bin/env python3
"""Resultados de la segunda iteración para el paper v8 (14-nov-2026).
Lee los CSV de ../datos/14nov, calcula tasas con IC de Wilson, McNemar exacto y mid-p sobre las escenas
pareadas del brazo, Fisher y la diferencia de Newcombe en las misiones, y escribe res_v8.json (marcadores @@...@@ de armar_v8.py)
y la figura salidas/fig_v2_resultados_v8.png.
Uso: python resultados_v8.py [carpeta_datos]
Solo entran las tandas válidas: las de afectadas_carga_14nov/ (Nav2 sin CPU, 40 vCPU con 3-4 simulaciones) quedan fuera por criterio horario."""
import csv, glob, json, math, os, sys, collections
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

G = os.path.dirname(os.path.abspath(__file__))
DAT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(G, '..', 'datos', '14nov')
FIG = os.path.join(G, 'salidas')


def leer(f):
    return list(csv.DictReader(open(f, encoding='utf-8')))


def wilson(s, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = s / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z / d * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, c - h), min(1.0, c + h)


def ic(s, n):
    lo, hi = wilson(s, n); return f'{100 * lo:.0f}-{100 * hi:.0f} %'


def pct(s, n):
    return f'{100 * s / n:.0f}' if n else '—'


def binom_cdf(k, n):
    return sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n


def mcnemar(b, c):
    n = b + c; k = min(b, c)
    if n == 0:
        return 1.0, 1.0
    exacto = min(1.0, 2 * binom_cdf(k, n))
    midp = exacto - math.comb(n, k) / 2 ** n            # Fagerland et al. 2013: mid-p = p exacto − P(X = k)
    return exacto, midp


def fisher(a, n1, c, n2):
    """Fisher exacto bilateral para 2x2 (a éxitos de n1 frente a c de n2)."""
    N, K = n1 + n2, a + c
    pr = lambda x: math.comb(K, x) * math.comb(N - K, n1 - x) / math.comb(N, n1)
    p0 = pr(a)
    return min(1.0, sum(pr(x) for x in range(max(0, K - n2), min(K, n1) + 1) if pr(x) <= p0 * (1 + 1e-9)))


def newcombe(a, n1, c, n2):
    l1, u1 = wilson(a, n1); l2, u2 = wilson(c, n2); p1, p2 = a / n1, c / n2; d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


RES = {}
# ------------------------------------------------------------------ banco pareado del brazo (50 escenas, semilla 900)
def por_escena(f, est):
    return {int(r['escena']): int(r['exito'] or 0) for r in leer(f) if r['estrategia'] == est}


f2 = os.path.join(DAT, 'eval_brazo_A7e2_40k_n50_s900.csv')
f10 = os.path.join(DAT, 'eval_escena_definitivo_n50_FINAL_2026-11-13.csv')
f10_40 = os.path.join(DAT, 'eval_escena_40k_n50_2026-11-13.csv')
fpo = os.path.join(DAT, 'eval_brazo_A7e2_po40k_n50_s900.csv')
brazo = [('Experto clásico', '10 N·m', por_escena(f10, 'ik_directa')),
         ('SmolVLA 20k pasos', '10 N·m', por_escena(f10, 'vla')),
         ('SmolVLA 40k pasos', '10 N·m', por_escena(f10_40, 'vla')),
         ('Experto clásico', '2 N·m', por_escena(f2, 'ik_directa')),
         ('SmolVLA 40k pasos', '2 N·m', por_escena(f2, 'vla'))]
HAY_PO = os.path.exists(fpo) and len(por_escena(fpo, 'vla')) >= 50
if HAY_PO:
    brazo.append(('SmolVLA 40k, pinza = orden', '2 N·m', por_escena(fpo, 'vla')))
exp2 = brazo[3][2]


def pares(a, b):
    comunes = sorted(set(a) & set(b))
    return sum(1 for k in comunes if a[k] and not b[k]), sum(1 for k in comunes if b[k] and not a[k]), len(comunes)


filas = [['Política', 'Pinza', 'Éxito', 'IC 95 %', 'b/c y p medio']]
for nom, fz, d in brazo:
    if nom == 'SmolVLA 20k pasos':
        continue
    s, n = sum(d.values()), len(d)
    ref = brazo[0][2] if fz == '10 N·m' else exp2
    if d is ref:
        cmp_ = '—'
    else:
        b, c, _ = pares(ref, d); ex, mp = mcnemar(b, c); cmp_ = f'{b}/{c}, {mp:.3f}'.replace('0.', '0.')
    filas.append([nom, fz, f'{s}/{n}', ic(s, n), cmp_])
RES['b_tabla'] = ',\n'.join('    ' + json.dumps(f, ensure_ascii=False) for f in filas)
b, c, nb = pares(exp2, brazo[4][2]); ex, mp = mcnemar(b, c)
RES.update(b_v=sum(brazo[4][2].values()), b_e=sum(exp2.values()), b_n=nb, b_b=b, b_c=c, b_pex=f'{ex:.3f}', b_pmid=f'{mp:.3f}',
           b_ic_v=ic(sum(brazo[4][2].values()), nb), b_ic_e=ic(sum(exp2.values()), nb))
b10, c10, _ = pares(brazo[0][2], brazo[2][2]); ex10, mp10 = mcnemar(b10, c10)
RES.update(b10_v=sum(brazo[2][2].values()), b10_e=sum(brazo[0][2].values()), b10_b=b10, b10_c=c10, b10_pex=f'{ex10:.2f}', b10_pmid=f'{mp10:.2f}',
           b10_20=sum(brazo[1][2].values()))
ms = [float(r['ms_inferencia']) for r in leer(f2) if r['estrategia'] == 'vla' and r.get('ms_inferencia') not in (None, '')]
RES['b_ms'] = f'{sum(ms) / len(ms):.0f}' if ms else '—'
if HAY_PO:
    po = brazo[5][2]; bp, cp, _ = pares(exp2, po); exp_, mpp = mcnemar(bp, cp); bv, cv, _ = pares(brazo[4][2], po); exv, mpv = mcnemar(bv, cv)
    RES.update(po_s=sum(po.values()), po_ic=ic(sum(po.values()), len(po)), po_b=bp, po_c=cp, po_pmid=f'{mpp:.3f}', po_bv=bv, po_cv=cv, po_pmid_v=f'{mpv:.3f}')

# ------------------------------------------------------------------ misiones completas (configuración A7e2)
def misiones(prefijo):
    fs = sorted(glob.glob(os.path.join(DAT, f'final_misiones_{prefijo}_A7e2_n20_s*.csv')))
    rows = [r for f in fs for r in leer(f)]
    sem = [os.path.basename(f).split('_s')[-1].split('.')[0] for f in fs]
    return rows, sem


ETAPAS = [('Ir a la zona de recojo', 'nav_recojo'), ('Acercar y recoger', 'recoger'), ('Ir a la zona de entrega', 'nav_entrega'), ('Colocar en el plato', 'colocar')]
POL = [('experto', 'Experto'), ('vla40k', 'SmolVLA 40k')]
if glob.glob(os.path.join(DAT, 'final_misiones_vlapo40k_A7e2_n20_s*.csv')):
    POL.append(('vlapo40k', 'SmolVLA pinza = orden'))
M = {}
for k, nom in POL:
    rows, sem = misiones(k)
    if not rows:
        continue
    n = len(rows); ok = sum(int(r['exito'] or 0) for r in rows); fallo = collections.Counter(r['etapa_fallo'] for r in rows if r['etapa_fallo'])
    llegan, etapas = n, []
    for et, clave in ETAPAS:
        f_ = fallo.get(clave, 0); etapas.append((llegan - f_, llegan)); llegan -= f_
    t = [float(r['total_s']) for r in rows if int(r['exito'] or 0) and r.get('total_s')]
    e = [float(r['cubo_err_plato_mm']) for r in rows if int(r['exito'] or 0) and r.get('cubo_err_plato_mm')]
    M[k] = dict(nom=nom, n=n, ok=ok, sem=sem, etapas=etapas, t=sum(t) / len(t) if t else float('nan'), e=sum(e) / len(e) if e else float('nan'), fallo=fallo)

ex_, vl = M['experto'], M['vla40k']
fil = [['Etapa'] + [f'{M[k]["nom"]}' for k, _ in POL if k in M]]
for i, (et, _) in enumerate(ETAPAS):
    fil.append([et] + [f'{M[k]["etapas"][i][0]}/{M[k]["etapas"][i][1]}' for k, _ in POL if k in M])
fil.append(['Misión completa'] + [f'{M[k]["ok"]}/{M[k]["n"]} ({pct(M[k]["ok"], M[k]["n"])} %)' for k, _ in POL if k in M])
fil.append(['IC 95 %'] + [ic(M[k]['ok'], M[k]['n']) for k, _ in POL if k in M])
fil.append(['Duración (s)'] + [f'{M[k]["t"]:.0f}' for k, _ in POL if k in M])
RES['m_tabla'] = ',\n'.join('    ' + json.dumps(f, ensure_ascii=False) for f in fil)
d, lo, hi = newcombe(ex_['ok'], ex_['n'], vl['ok'], vl['n'])
# fallos de navegación: mismas semillas y mismas condiciones de carga (las tandas del VLA 40k corrieron con 3 simulaciones; las últimas del experto con 1)
def nav_fallos(prefijo, semillas):
    rows = [r for s_ in semillas for r in leer(os.path.join(DAT, f'final_misiones_{prefijo}_A7e2_n20_s{s_}.csv'))]
    return sum(1 for r in rows if r['etapa_fallo'] in ('nav_recojo', 'nav_entrega')), len(rows)
comunes = [s_ for s_ in vl['sem'] if s_ in ex_['sem']]
(nav_e, n_nav_e), (nav_v, n_nav_v) = nav_fallos('experto', comunes), nav_fallos('vla40k', comunes)
RES['m_nav_sem'] = f'{comunes[0]}-{comunes[-1]}'
ag_v = vl['etapas'][1]; ag_e = ex_['etapas'][1]
post_v = (vl['ok'], ag_v[0])            # misiones completadas cuando el VLA levantó el cubo
RES.update(me_n=ex_['n'], me_ok=ex_['ok'], me_pct=pct(ex_['ok'], ex_['n']), me_ic=ic(ex_['ok'], ex_['n']), me_sem=f'{ex_["sem"][0]}-{ex_["sem"][-1]}',
           mv_n=vl['n'], mv_ok=vl['ok'], mv_pct=pct(vl['ok'], vl['n']), mv_ic=ic(vl['ok'], vl['n']), mv_sem=f'{vl["sem"][0]}-{vl["sem"][-1]}',
           m_dif=f'{100 * d:.0f}', m_dif_ic=f'{100 * lo:.0f}-{100 * hi:.0f}', m_pfisher=f'{fisher(ex_["ok"], ex_["n"], vl["ok"], vl["n"]):.1e}'.replace('e-0', '·10⁻'),
           m_nav_e=nav_e, m_nav_v=nav_v, m_pnav=f'{fisher(nav_e, n_nav_e, nav_v, n_nav_v):.2f}', m_nav_n=n_nav_e,
           m_ag_v=f'{ag_v[0]}/{ag_v[1]}', m_ag_v_pct=pct(*ag_v), m_ag_e=f'{ag_e[0]}/{ag_e[1]}', m_ag_e_pct=pct(*ag_e),
           m_post_v=f'{post_v[0]}/{post_v[1]}', m_err_e=f'{ex_["e"] / 10:.1f}', m_t_e=f'{ex_["t"]:.0f}', m_t_v=f'{vl["t"]:.0f}',
           m_pag=f'{fisher(ag_v[0], ag_v[1], RES["b_v"], RES["b_n"]):.2f}', hay_po=int(HAY_PO))
if 'vlapo40k' in M:
    po = M['vlapo40k']; RES.update(mp_n=po['n'], mp_ok=po['ok'], mp_pct=pct(po['ok'], po['n']), mp_ic=ic(po['ok'], po['n']))

json.dump(RES, open(os.path.join(G, 'salidas', 'res_v8.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ------------------------------------------------------------------ figura: (a) banco del brazo, (b) misión por etapas
C = {'experto': '#2a78d6', 'vla40k': '#eb6834', 'vlapo40k': '#1baf7a'}
TXT, TXT2, GRID = '#0b0b0b', '#52514e', '#e4e3df'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.edgecolor': TXT2, 'axes.labelcolor': TXT, 'xtick.color': TXT2, 'ytick.color': TXT2})
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={'width_ratios': [1, 1.35]})


def barra(ax, x, s, n, color, w):
    p = s / n; lo, hi = wilson(s, n)
    ax.bar(x, 100 * p, w, color=color, edgecolor='white', linewidth=1.5, zorder=2)
    ax.errorbar(x, 100 * p, yerr=[[max(0.0, 100 * (p - lo))], [max(0.0, 100 * (hi - p))]], fmt='none', ecolor=TXT2, elinewidth=0.8, capsize=2, zorder=3)
    ax.text(x, 3, f'{s}/{n}', ha='center', va='bottom', fontsize=6.5, color='white', fontweight='bold', rotation=90, zorder=4)


grupos = [('10 N·m', [(0, 'experto'), (2, 'vla40k')]), ('2 N·m', [(3, 'experto'), (4, 'vla40k')] + ([(5, 'vlapo40k')] if HAY_PO else []))]
x0 = 0
for g, items in grupos:
    for j, (i, k) in enumerate(items):
        d_ = brazo[i][2]; barra(a1, x0 + j * 0.3, sum(d_.values()), len(d_), C[k], 0.27)
    a1.text(x0 + 0.3 * (len(items) - 1) / 2, -14, f'pinza {g}', ha='center', fontsize=7.5, color=TXT)
    x0 += 0.3 * len(items) + 0.35
a1.set_ylim(0, 105); a1.set_xticks([]); a1.set_ylabel('Éxito (%)'); a1.set_title('(a) Agarre, 50 escenas pareadas', fontsize=8.5, color=TXT, loc='left')
for k_, nom in POL:
    if k_ in M:
        n_ = len(M[k_]['etapas'])
        for i in range(n_ + 1):
            s, n = (M[k_]['etapas'][i] if i < n_ else (M[k_]['ok'], M[k_]['n']))
            off = [-0.27, 0, 0.27][[k for k, _ in POL if k in M].index(k_)] if len(M) == 3 else [-0.17, 0.17][[k for k, _ in POL if k in M].index(k_)]
            barra(a2, i + off, s, n, C[k_], 0.3 if len(M) == 2 else 0.25)
a2.set_xticks(range(5)); a2.set_xticklabels(['Nav. al\nrecojo', 'Acercar y\nrecoger', 'Nav. a la\nentrega', 'Colocar', 'Misión\ncompleta'], fontsize=7)
a2.set_ylim(0, 105); a2.set_title('(b) Misión por etapas', fontsize=8.5, color=TXT, loc='left')
for ax in (a1, a2):
    ax.yaxis.grid(True, color=GRID, linewidth=0.6, zorder=0); ax.set_axisbelow(True)
    for s_ in ('top', 'right'):
        ax.spines[s_].set_visible(False)
from matplotlib.patches import Patch
ley = [Patch(color=C['experto'], label='Experto clásico'), Patch(color=C['vla40k'], label='SmolVLA 40k')] + ([Patch(color=C['vlapo40k'], label='SmolVLA 40k, pinza = orden')] if (HAY_PO or 'vlapo40k' in M) else [])
fig.legend(handles=ley, loc='lower center', ncol=len(ley), frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(os.path.join(FIG, 'fig_v2_resultados_v8.png'), dpi=220, bbox_inches='tight')
print('res_v8.json y fig_v2_resultados_v8.png escritos;', {k: v for k, v in RES.items() if not k.endswith('tabla')})
