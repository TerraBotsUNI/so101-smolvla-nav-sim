#!/usr/bin/env python3
"""Resultados para el paper v13 (resultados de manipulación, 16-nov-2026).
1) Reutiliza TODO el cálculo de la v10 ejecutando resultados_v10.py hasta antes de escribir res_v10.json (no escribe nada de la v10).
2) Añade lo medido entre el 15-nov (tarde) y el 16-nov (madrugada), recalculado desde los CSV de ../datos/16nov/
   (traídos de la WS en solo lectura):
   - bancos de agarre s900 (disposición de demostración) y s910 (disposición de misión): experto clásico con m = 26 mm, SmolVLA v2,
     SmolVLA 40k (s910), ACT; referencia s900 = eval_brazo_A7e2_40k_n50_s900.csv (experto 18 mm y SmolVLA 40k). Se comprueba que cada escena
     tenga el mismo color pedido y la misma disposición de cubos en los dos archivos que se comparan. McNemar exacto (principal) y mid-p;
   - éxito en s910 por posición del cubo pedido en la fila (coordenada y del pedido frente a la de los otros dos: menor y = derecha);
   - misiones finales (semillas 21-24) del experto con 26 mm y de SmolVLA v2, pareadas entre sí y con las de la receta anterior
     (experto 18 mm, SmolVLA 40k), por etapa; caída del cubo durante el transporte (cubo_sujeto = 0 al llegar a la entrega);
     éxito condicionado a haber levantado el cubo; fallos de navegación por tanda frente a los avisos de MPPI («missed rate») de
     ESTADO_NOCHE15.txt (correlación de rangos de Spearman, descriptiva).
   La tabla de misiones incluye también el modelo con la pinza reetiquetada (vlapo40k, datos de 14nov) en las mismas semillas.
3) Escribe res_v13.json y salidas/fig_v2_posicion_margen_v13.png ((a) recogida en misión por posición, (b) banco s910 por posición,
   (c) barrido del margen).
Uso: python resultados_v13.py"""
import csv, json, math, os, re, statistics, sys

G = os.path.dirname(os.path.abspath(__file__))
D16 = os.path.join(G, '..', 'datos', '16nov')
FIG = os.path.join(G, 'salidas')

src = open(os.path.join(G, 'resultados_v10.py'), encoding='utf-8').read()
corte = src.index("json.dump(RES, open(os.path.join(G, 'salidas', 'res_v10.json')")
ns = {'__file__': os.path.join(G, 'resultados_v10.py'), '__name__': 'resultados_v10_parcial'}
_argv = sys.argv; sys.argv = [sys.argv[0]]
exec(compile(src[:corte], 'resultados_v10.py', 'exec'), ns)
sys.argv = _argv
RES, leer, wilson, mcnemar = (ns[k] for k in ('RES', 'leer', 'wilson', 'mcnemar'))
EST9 = ns['ns']['EST']; BAR = ns['ns']['BAR']; MARG = ns['ns']['MARG']     # recogida por posición (v9) y barrido del margen


def L(f):
    return leer(os.path.join(D16, f))


def ic(s, n):
    lo, hi = wilson(s, n); return f'{100 * lo:.0f}-{100 * hi:.0f} %'


def pfmt(p):
    if p >= 0.9995:
        return '1'
    if p >= 0.01:
        return f'{p:.3f}'
    if p >= 0.001:
        return f'{p:.4f}'
    m, e = f'{p:.1e}'.split('e'); return f'{m}·10^{int(e)}'


def mc(b, c):
    ex, mp = mcnemar(b, c); return pfmt(ex), pfmt(mp)


# ------------------------------------------------------------------ bancos
BANCOS = {  # clave: (archivo, estrategia)
    'e18_900': ('eval_brazo_A7e2_40k_n50_s900.csv', 'ik_directa'), 'v40_900': ('eval_brazo_A7e2_40k_n50_s900.csv', 'vla'),
    'e26_900': ('eval_brazo_v2_demo_s900.csv', 'ik_directa'), 'v2_900': ('eval_brazo_v2_demo_s900.csv', 'vla'),
    'act_900': ('eval_brazo_act_demo_s900.csv', 'vla'),
    'e26_910': ('eval_brazo_v2_mision_s910.csv', 'ik_directa'), 'v2_910': ('eval_brazo_v2_mision_s910.csv', 'vla'),
    'v40_910': ('eval_brazo_40k_mision_s910.csv', 'vla'), 'act_910': ('eval_brazo_act_mision_s910.csv', 'vla'),
}


def posicion(r):
    y = {}
    for t in r['cubos'].split(';'):
        c, v = t.split(':'); y[c] = float(v.split(',')[1])
    ys = sorted(y.values()); yp = y[r['color']]
    return 2 if yp == ys[0] else (0 if yp == ys[-1] else 1)   # 0 izquierda, 1 centro, 2 derecha (menor y = derecha)


B = {}
for k, (f, e) in BANCOS.items():
    rows = [r for r in L(f) if r['estrategia'] == e]
    assert len(rows) == 50 and len({r['escena'] for r in rows}) == 50, k
    B[k] = {int(r['escena']): r for r in rows}
    s = sum(int(r['exito']) for r in rows)
    RES[f'bk_{k}'] = f'{s}/50'; RES[f'bk_{k}_s'] = s; RES[f'bk_{k}_ic'] = ic(s, 50)
    if k.endswith('910'):
        pc = [[0, 0] for _ in range(3)]
        for r in rows:
            p = posicion(r); pc[p][1] += 1; pc[p][0] += int(r['exito'])
        for i, lado in enumerate('icd'):
            RES[f'bk_{k}_{lado}'] = f'{pc[i][0]}/{pc[i][1]}'
        RES[f'bk_{k}_pos'] = pc


def par(a, b):
    A, Bb = B[a], B[b]; assert set(A) == set(Bb)
    for i in A:
        assert (A[i]['color'], A[i]['cubos']) == (Bb[i]['color'], Bb[i]['cubos']), (a, b, i)
    x = sum(int(A[i]['exito']) and not int(Bb[i]['exito']) for i in A); y = sum(int(Bb[i]['exito']) and not int(A[i]['exito']) for i in A)
    pe, pm = mc(x, y); clave = f'mc_{a}__{b}'
    RES.update({clave + '_b': x, clave + '_c': y, clave + '_pex': pe, clave + '_pmid': pm})
    return x, y


for a, b in (('e26_900', 'v2_900'), ('v2_900', 'v40_900'), ('e26_900', 'e18_900'), ('v2_900', 'act_900'), ('v40_900', 'act_900'),
             ('e26_900', 'act_900'), ('e26_910', 'v2_910'), ('v2_910', 'v40_910'), ('v2_910', 'act_910'), ('v40_910', 'act_910'),
             ('e26_910', 'v40_910')):
    par(a, b)

# ------------------------------------------------------------------ misiones (semillas 21-24)
SEM = (21, 22, 23, 24)
POLM = {'e18': 'experto', 'v40': 'vla40k', 'po': 'vlapo40k', 'e26': 'experto_m26', 'v2': 'vlav2'}
D14 = os.path.join(G, '..', 'datos', '14nov')    # la pinza reetiquetada (vlapo40k) solo está en 14nov
M = {k: {s: (leer(os.path.join(D14, f'final_misiones_{p}_A7e2_n20_s{s}.csv')) if k == 'po' else L(f'final_misiones_{p}_A7e2_n20_s{s}.csv')) for s in SEM}
     for k, p in POLM.items()}
for k in POLM:
    for s in SEM:
        assert len(M[k][s]) == 20, (k, s)
        for x, y in zip(M[k][s], M['e18'][s]):
            assert (x['mision'], x['color'], x['orden_cubos']) == (y['mision'], y['color'], y['orden_cubos']), (k, s, x['mision'])
NAV = ('nav_recojo', 'nav_entrega')
TM = [['Etapa', 'Experto, 18 mm', 'SmolVLA 40k', 'SmolVLA, pinza = orden', 'Experto, 26 mm', 'SmolVLA v2']]
fil = {n: [n] for n in ('Llega a la zona de recojo', 'Acerca y levanta el cubo', 'Llega a la zona de entrega', 'Cubo sujeto al llegar',
                        'Misión completa', 'IC 95 %', 'Completa si levantó', 'Duración (s)')}
for k in POLM:
    R_ = [r for s in SEM for r in M[k][s]]
    n = len(R_); nav1 = sum(r['nav1_ok'] == '1' for r in R_); pk = sum(r['pick_ok'] == '1' for r in R_)
    nav2 = sum(r['nav2_ok'] == '1' for r in R_); suj = sum(r['nav2_ok'] == '1' and r['cubo_sujeto'] == '1' for r in R_)
    ok = sum(int(r['exito'] or 0) for r in R_)
    caida = [r for r in R_ if r['nav2_ok'] == '1' and r['cubo_sujeto'] == '0']
    lejos = [r for r in caida if float(r['cubo_err_plato_mm']) > 1000]
    okk = [r for r in R_ if r['exito'] == '1']; t = [float(r['total_s']) for r in okk]
    fallo_suj = [r for r in R_ if r['etapa_fallo'] == 'colocar' and r['cubo_sujeto'] == '1']
    navf = sum(r['etapa_fallo'] in NAV for r in R_)
    RES.update({f'mf_{k}_n': n, f'mf_{k}_ok': ok, f'mf_{k}_pct': f'{100 * ok / n:.2f}'.rstrip('0').rstrip('.'), f'mf_{k}_ic': ic(ok, n),
                f'mf_{k}_pick': pk, f'mf_{k}_nav2': nav2, f'mf_{k}_caida': len(caida), f'mf_{k}_lejos': len(lejos),
                f'mf_{k}_condic': f'{ok}/{pk}', f'mf_{k}_condic_pct': f'{100 * ok / pk:.1f}', f'mf_{k}_navf': navf,
                f'mf_{k}_navf_sem': [sum(r['etapa_fallo'] in NAV for r in M[k][s]) for s in SEM],
                f'mf_{k}_ok_sem': [sum(int(r['exito'] or 0) for r in M[k][s]) for s in SEM],
                f'mf_{k}_rec': sum(r['etapa_fallo'] == 'recoger' for r in R_),
                f'mf_{k}_colsuj': len(fallo_suj), f'mf_{k}_colsuj_cm': sorted(round(float(r['cubo_err_plato_mm']) / 10) for r in fallo_suj),
                f'mf_{k}_lejos_m': sorted(round(float(r['cubo_err_plato_mm']) / 1000, 2) for r in lejos),
                f'mf_{k}_dur': f'{statistics.mean(t):.0f} ± {statistics.stdev(t):.0f}',
                f'mf_{k}_plato': f'{statistics.mean(float(r["cubo_err_plato_mm"]) / 10 for r in okk):.1f} ± {statistics.stdev(float(r["cubo_err_plato_mm"]) / 10 for r in okk):.1f}'})
    fil['Llega a la zona de recojo'].append(f'{nav1}/{n}'); fil['Acerca y levanta el cubo'].append(f'{pk}/{nav1}')
    fil['Llega a la zona de entrega'].append(f'{nav2}/{pk}'); fil['Cubo sujeto al llegar'].append(f'{suj}/{nav2}')
    fil['Misión completa'].append(f'{ok}/{n} ({100 * ok / n:.0f} %)')
    fil['IC 95 %'].append(ic(ok, n)); fil['Completa si levantó'].append(f'{ok}/{pk} ({100 * ok / pk:.0f} %)')
    fil['Duración (s)'].append(f'{statistics.mean(t):.0f} ± {statistics.stdev(t):.0f}')
    # recogida en misión por posición (misiones que llegaron a la zona de recojo)
    pc = [[0, 0] for _ in range(3)]
    for r in R_:
        if r['nav1_ok'] == '1':
            p = r['orden_cubos'].split('-').index(r['color']); pc[p][1] += 1; pc[p][0] += r['etapa_fallo'] != 'recoger'
    RES[f'mf_{k}_pos'] = pc
    for i, lado in enumerate('icd'):
        RES[f'mf_{k}_pos_{lado}'] = f'{pc[i][0]}/{pc[i][1]}'
TM += list(fil.values()); RES['mf_tabla'] = TM


def parm(a, b, cond):
    x = y = 0
    for s in SEM:
        for u, v in zip(M[a][s], M[b][s]):
            ca, cb = cond(u), cond(v); x += ca and not cb; y += cb and not ca
    pe, pm = mc(x, y); return x, y, pe, pm


exito = lambda r: r['exito'] == '1'
for a, b in (('e26', 'v2'), ('e26', 'e18'), ('v2', 'v40'), ('v2', 'e18')):
    x, y, pe, pm = parm(a, b, exito)
    RES.update({f'pm_{a}_{b}_b': x, f'pm_{a}_{b}_c': y, f'pm_{a}_{b}_pex': pe, f'pm_{a}_{b}_pmid': pm})
x, y, pe, pm = parm('e26', 'v2', lambda r: r['etapa_fallo'] in NAV)
RES.update(pmnav_b=x, pmnav_c=y, pmnav_pex=pe, pmnav_pmid=pm)
x, y, pe, pm = parm('e26', 'v2', lambda r: r['nav2_ok'] == '1' and r['cubo_sujeto'] == '0')
RES.update(pmcaida_b=x, pmcaida_c=y, pmcaida_pex=pe, pmcaida_pmid=pm)

# ------------------------------------------------------------------ carga de CPU: avisos de MPPI por tanda (ESTADO_NOCHE15.txt)
AV = {}
for lin in open(os.path.join(D16, 'ESTADO_NOCHE15.txt'), encoding='utf-8'):
    m = re.search(r'(experto 26 mm|VLA v2) semilla (\d+): (\d+)/20; avisos Nav2: (\d+)', lin)
    if m:
        k = 'e26' if m.group(1).startswith('experto') else 'v2'
        AV[(k, int(m.group(2)))] = (int(m.group(3)), int(m.group(4)))
pts = []
for k in ('e26', 'v2'):
    for i, s in enumerate(SEM):
        assert AV[(k, s)][0] == RES[f'mf_{k}_ok_sem'][i], (k, s)            # el estado coincide con el CSV
        pts.append((AV[(k, s)][1], RES[f'mf_{k}_navf_sem'][i], k, s))


def rangos(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for t in range(i, j + 1):
            r[o[t]] = (i + j) / 2 + 1
        i = j + 1
    return r


ra, rb = rangos([p[0] for p in pts]), rangos([p[1] for p in pts])
ma, mb = statistics.mean(ra), statistics.mean(rb)
rho = sum((u - ma) * (v - mb) for u, v in zip(ra, rb)) / math.sqrt(sum((u - ma) ** 2 for u in ra) * sum((v - mb) ** 2 for v in rb))
alto = [p for p in pts if p[0] >= 100]; bajo = [p for p in pts if p[0] < 100]
RES.update(cpu_rho=f'{rho:.2f}', cpu_tandas=len(pts), cpu_av_min=min(p[0] for p in pts), cpu_av_max=max(p[0] for p in pts),
           cpu_alto_n=len(alto), cpu_alto_navf=sum(p[1] for p in alto), cpu_alto_mis=20 * len(alto),
           cpu_bajo_n=len(bajo), cpu_bajo_navf=sum(p[1] for p in bajo), cpu_bajo_mis=20 * len(bajo),
           cpu_pts=[list(p) for p in pts])

json.dump(RES, open(os.path.join(G, 'salidas', 'res_v13.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ------------------------------------------------------------------ figura v13
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
C = {'exp': '#2a78d6', 'v40': '#eb6834', 'v2': '#1baf7a', 'act': '#eda100'}
TXT, TXT2, GRID = '#0b0b0b', '#52514e', '#e4e3df'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.edgecolor': TXT2, 'axes.labelcolor': TXT, 'xtick.color': TXT2, 'ytick.color': TXT2})
fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(7.2, 2.0), gridspec_kw={'width_ratios': [1, 1.2, 1]})


def barra(ax, x, s, n, color, w, oscuro=False):
    p = s / n; lo, hi = wilson(s, n)
    ax.bar(x, 100 * p, w, color=color, edgecolor='white', linewidth=1.0, zorder=2)
    ax.errorbar(x, 100 * p, yerr=[[max(0.0, 100 * (p - lo))], [max(0.0, 100 * (hi - p))]], fmt='none', ecolor=TXT2, elinewidth=0.7, capsize=1.6, zorder=3)
    dentro = p >= 0.35
    ax.text(x, 3 if dentro else 100 * hi + 2, f'{s}/{n}', ha='center', va='bottom', fontsize=5.6, rotation=90, zorder=4, fontweight='bold',
            color=(TXT if oscuro else 'white') if dentro else TXT2)


LAD = ['Izq.', 'Centro', 'Der.']
for j, (est, col) in enumerate(((EST9['experto'], C['exp']), (EST9['vla40k'], C['v40']), (RES['mf_v2_pos'], C['v2']))):
    for i in range(3):
        barra(a1, i + (j - 1) * 0.28, est[i][0], est[i][1], col, 0.26)
for j, (k, col) in enumerate((('e26_910', C['exp']), ('v40_910', C['v40']), ('act_910', C['act']), ('v2_910', C['v2']))):
    for i in range(3):
        s, n = RES[f'bk_{k}_pos'][i]; barra(a2, i + (j - 1.5) * 0.21, s, n, col, 0.2, oscuro=(k == 'act_910'))
for i, m in enumerate(MARG):
    barra(a3, i - 0.17, BAR[(m, 0)][0], 30, '#8a8984', 0.3)
    barra(a3, i + 0.17, BAR[(m, 3)][0], 30, C['exp'], 0.3)
for ax, tit, xt in ((a1, '(a) Recogida en misión', LAD), (a2, '(b) Banco s910', LAD), (a3, '(c) Experto: margen $m$', [f'{m}' for m in MARG])):
    ax.set_xticks(range(len(xt))); ax.set_xticklabels(xt, fontsize=7.2); ax.set_ylim(0, 120); ax.set_yticks(range(0, 101, 20))
    ax.set_title(tit, fontsize=8, color=TXT, loc='left'); ax.yaxis.grid(True, color=GRID, linewidth=0.6, zorder=0); ax.set_axisbelow(True)
    for s_ in ('top', 'right'):
        ax.spines[s_].set_visible(False)
a1.set_ylabel('Éxito (%)'); a3.set_xlabel('mm', fontsize=7, labelpad=1)
ley = [Patch(color=C['exp'], label='Experto (a: 18 mm; b: 26 mm)'), Patch(color=C['v40'], label='SmolVLA 40k'), Patch(color=C['act'], label='ACT'),
       Patch(color=C['v2'], label='SmolVLA v2'), Patch(color='#8a8984', label='(c) sin ruido'), Patch(color=C['exp'], label='(c) ruido ±3 mm, ±10°')]
fig.legend(handles=ley, loc='lower center', ncol=6, frameon=False, fontsize=6.0, bbox_to_anchor=(0.5, -0.02), handlelength=1.2, columnspacing=0.9)
fig.tight_layout(rect=(0, 0.08, 1, 1), w_pad=0.6)
fig.savefig(os.path.join(FIG, 'fig_v2_posicion_margen_v13.png'), dpi=220, bbox_inches='tight')
print('res_v13.json y fig_v2_posicion_margen_v13.png escritos;',
      {k: v for k, v in RES.items() if k.startswith(('bk_', 'mc_', 'mf_', 'pm_', 'pmnav', 'pmcaida', 'cpu_')) and not k.endswith(('tabla', 'pts'))})
