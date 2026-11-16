#!/usr/bin/env python3
"""Resultados para el paper v9 (primera versión, 15-nov-2026).
1) Reutiliza TODO el cálculo de la v8 ejecutando el código de resultados_v8.py hasta antes de escribir res_v8.json (no escribe nada de la v8:
   ni res_v8.json ni fig_v2_resultados_v8.png).
2) Añade lo medido el 15-nov:
   - ablación de acciones ejecutadas por inferencia (SmolVLA 40k, banco s900: 25 / 15 / 10 acciones) con McNemar por escena frente a 25;
   - estratificación de la recogida en misión por la posición del cubo pedido en la fila (columna orden_cubos; solo misiones con nav1_ok = 1);
   - barrido del margen del experto (banco con disposición de misión, semilla 910, 30 escenas, sin ruido y con ruido ±3 mm / ±10°).
3) Escribe res_v9.json y la figura salidas/fig_v2_posicion_margen_v9.png.
Uso: python resultados_v9.py [carpeta_datos_14nov] [carpeta_datos_15nov]"""
import csv, glob, json, math, os, sys, collections

G = os.path.dirname(os.path.abspath(__file__))
D14 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(G, '..', 'datos', '14nov')
D15 = sys.argv[2] if len(sys.argv) > 2 else os.path.join(G, '..', 'datos', '15nov')
FIG = os.path.join(G, 'salidas')

# ------------------------------------------------------------------ 1) cálculo de la v8 sin sus salidas
src = open(os.path.join(G, 'resultados_v8.py'), encoding='utf-8').read()
corte = src.index("json.dump(RES, open(os.path.join(G, 'salidas', 'res_v8.json')")
ns = {'__file__': os.path.join(G, 'resultados_v8.py'), '__name__': 'resultados_v8_parcial'}
_argv = sys.argv; sys.argv = [sys.argv[0], D14]
exec(compile(src[:corte], 'resultados_v8.py', 'exec'), ns)
sys.argv = _argv
RES, leer, wilson, ic, pct, mcnemar, fisher, por_escena, pares = (ns[k] for k in ('RES', 'leer', 'wilson', 'ic', 'pct', 'mcnemar', 'fisher', 'por_escena', 'pares'))
plt = ns['plt']

# ------------------------------------------------------------------ 2a) ablación de acciones por inferencia (sin reentrenar)
v25 = por_escena(os.path.join(D14, 'eval_brazo_A7e2_40k_n50_s900.csv'), 'vla')
filas = [['Acciones por inferencia', 'Éxito', 'IC 95 %', 'b/c', 'p exacto', 'p medio']]
filas.append(['25 (referencia)', f'{sum(v25.values())}/{len(v25)}', ic(sum(v25.values()), len(v25)), '—', '—', '—'])
for na in (15, 10):
    d = por_escena(os.path.join(D15, f'eval_brazo_A7e2_40k_nacc{na}_n50_s900.csv'), 'vla')
    assert len(d) == 50, (na, len(d))
    b, c, n = pares(v25, d); ex, mp = mcnemar(b, c)
    RES.update({f'na{na}_s': sum(d.values()), f'na{na}_ic': ic(sum(d.values()), n), f'na{na}_b': b, f'na{na}_c': c,
                f'na{na}_pex': f'{ex:.3f}', f'na{na}_pmid': f'{mp:.3f}'})
    filas.append([str(na), f'{sum(d.values())}/{n}', ic(sum(d.values()), n), f'{b}/{c}', f'{ex:.3f}', f'{mp:.3f}'])
RES['na_tabla'] = filas
RES['na25_s'] = sum(v25.values())

# ------------------------------------------------------------------ 2b) recogida en misión por posición del cubo pedido
POS = ['Extremo izquierdo', 'Centro', 'Extremo derecho']
POLS = [('experto', 'Experto'), ('vla40k', 'SmolVLA 40k'), ('vlapo40k', 'SmolVLA pinza = orden')]
EST = {}
for k, nom in POLS:
    c = [[0, 0] for _ in range(3)]
    for f in sorted(glob.glob(os.path.join(D14, f'final_misiones_{k}_A7e2_n20_s*.csv'))):
        for r in leer(f):
            if r['nav1_ok'] != '1':
                continue                                   # solo las misiones que llegaron a la zona de recojo
            pos = r['orden_cubos'].split('-').index(r['color'])
            c[pos][1] += 1; c[pos][0] += 0 if r['etapa_fallo'] == 'recoger' else 1
    EST[k] = c
fil = [['Posición del cubo pedido'] + [nom for _, nom in POLS]]
for i, pnom in enumerate(POS):
    fil.append([pnom] + [f'{EST[k][i][0]}/{EST[k][i][1]}' for k, _ in POLS])
fil.append(['Total'] + [f'{sum(x[0] for x in EST[k])}/{sum(x[1] for x in EST[k])}' for k, _ in POLS])
RES['pos_tabla'] = fil
for k, _ in POLS:
    for i, s in enumerate(('i', 'c', 'd')):
        RES[f'pos_{k}_{s}'] = f'{EST[k][i][0]}/{EST[k][i][1]}'
# SmolVLA (ambos modelos juntos): extremo derecho frente a izquierdo y centro frente a izquierdo
vi = [EST['vla40k'][0][j] + EST['vlapo40k'][0][j] for j in (0, 1)]
vc = [EST['vla40k'][1][j] + EST['vlapo40k'][1][j] for j in (0, 1)]
vd = [EST['vla40k'][2][j] + EST['vlapo40k'][2][j] for j in (0, 1)]
p_di = fisher(vd[0], vd[1], vi[0], vi[1])
m_, e_ = f'{p_di:.1e}'.split('e')
RES.update(pos_v_i=f'{vi[0]}/{vi[1]}', pos_v_c=f'{vc[0]}/{vc[1]}', pos_v_d=f'{vd[0]}/{vd[1]}', pos_v_d_ic=ic(*vd), pos_v_c_ic=ic(*vc),
           pos_p_di=f'{m_}·10^{int(e_)}', pos_fallos_d=vd[1] - vd[0], pos_fallos_tot=(vi[1] - vi[0]) + (vc[1] - vc[0]) + (vd[1] - vd[0]),
           pos_n_tot=vi[1] + vc[1] + vd[1])
RES['pos_p_di_latex'] = f'{m_}\\cdot10^{{{int(e_)}}}'
# reparto de posiciones (comprobación de que la misión pone el pedido en cada posición con frecuencia parecida)
RES['pos_reparto_e'] = '/'.join(str(EST['experto'][i][1]) for i in range(3))

# ------------------------------------------------------------------ 2c) barrido del margen del experto (s910, disposición de misión)
MARG = [18, 22, 26, 30]
BAR = {}
for m in MARG:
    for r_ in (0, 3):
        f = os.path.join(D15, f'paso1_experto_m{m}_r{r_}_mision_s910.csv')
        rows = [r for r in leer(f) if r['estrategia'] == 'ik_directa']
        assert len(rows) == 30, (f, len(rows))
        BAR[(m, r_)] = (sum(int(r['exito'] or 0) for r in rows), len(rows))
fb = [['Margen $m$', 'Sin ruido', 'IC 95 %', 'Con ruido', 'IC 95 %']]
for m in MARG:
    a, b = BAR[(m, 0)], BAR[(m, 3)]
    fb.append([f'{m} mm', f'{a[0]}/{a[1]}', ic(*a), f'{b[0]}/{b[1]}', ic(*b)])
RES['bar_tabla'] = fb
# criterio fijado antes del barrido (vla/paso2_4.sh): mayor éxito con ruido; a igualdad, mayor sin ruido; a igualdad, el menor;
# se descarta el margen cuyo éxito sin ruido sea 2 o más escenas peor que el de 18 mm
cand = [m for m in MARG if BAR[(m, 0)][0] > BAR[(18, 0)][0] - 2]
elegido = sorted(cand, key=lambda m: (-BAR[(m, 3)][0], -BAR[(m, 0)][0], m))[0]
RES['bar_elegido'] = elegido
for m in MARG:
    RES[f'bar_{m}_0'] = f'{BAR[(m, 0)][0]}/30'; RES[f'bar_{m}_3'] = f'{BAR[(m, 3)][0]}/30'
RES['bar_18_26_p'] = f'{fisher(BAR[(26, 3)][0], 30, BAR[(18, 3)][0], 30):.2f}'
# mismas escenas en todo el barrido: comparación pareada 26 frente a 18 mm con ruido (McNemar)
e18 = {int(r['escena']): int(r['exito'] or 0) for r in leer(os.path.join(D15, 'paso1_experto_m18_r3_mision_s910.csv'))}
e26 = {int(r['escena']): int(r['exito'] or 0) for r in leer(os.path.join(D15, 'paso1_experto_m26_r3_mision_s910.csv'))}
b_, c_, _ = pares(e26, e18); ex_, mp_ = mcnemar(b_, c_)
RES.update(bar_mc_b=b_, bar_mc_c=c_, bar_mc_pex=f'{ex_:.3f}', bar_mc_pmid=f'{mp_:.3f}')
RES['pos_v_c_pct'] = pct(*vc)

json.dump(RES, open(os.path.join(G, 'salidas', 'res_v9.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ------------------------------------------------------------------ figura: (a) recogida por posición, (b) barrido del margen
C = {'experto': '#2a78d6', 'vla40k': '#eb6834', 'vlapo40k': '#1baf7a'}
TXT, TXT2, GRID = '#0b0b0b', '#52514e', '#e4e3df'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.edgecolor': TXT2, 'axes.labelcolor': TXT, 'xtick.color': TXT2, 'ytick.color': TXT2})
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.25), gridspec_kw={'width_ratios': [1.35, 1]})


def barra(ax, x, s, n, color, w):
    p = s / n; lo, hi = wilson(s, n)
    ax.bar(x, 100 * p, w, color=color, edgecolor='white', linewidth=1.2, zorder=2)
    ax.errorbar(x, 100 * p, yerr=[[max(0.0, 100 * (p - lo))], [max(0.0, 100 * (hi - p))]], fmt='none', ecolor=TXT2, elinewidth=0.8, capsize=2, zorder=3)
    ax.text(x, 104 if p < 0.15 else 3, f'{s}/{n}', ha='center', va='bottom', fontsize=6.3, color=TXT2 if p < 0.15 else 'white',
            fontweight='bold', rotation=90, zorder=4)


for j, (k, nom) in enumerate(POLS):
    for i in range(3):
        barra(a1, i + (j - 1) * 0.27, EST[k][i][0], EST[k][i][1], C[k], 0.25)
a1.set_xticks(range(3)); a1.set_xticklabels(['Extremo\nizquierdo', 'Centro', 'Extremo\nderecho'], fontsize=7.5)
a1.set_ylim(0, 118); a1.set_yticks(range(0, 101, 20)); a1.set_ylabel('Recogida (%)')
a1.set_title('(a) Recogida en misión por posición del pedido', fontsize=8.5, color=TXT, loc='left')
for i, m in enumerate(MARG):
    barra(a2, i - 0.17, BAR[(m, 0)][0], 30, '#8a8984', 0.3)
    barra(a2, i + 0.17, BAR[(m, 3)][0], 30, '#2a78d6', 0.3)
a2.set_xticks(range(4)); a2.set_xticklabels([f'{m} mm' for m in MARG], fontsize=7.5)
a2.set_ylim(0, 118); a2.set_yticks(range(0, 101, 20)); a2.set_ylabel('Éxito (%)'); a2.set_title('(b) Experto: barrido del margen $m$', fontsize=8.5, color=TXT, loc='left')
for ax in (a1, a2):
    ax.yaxis.grid(True, color=GRID, linewidth=0.6, zorder=0); ax.set_axisbelow(True)
    for s_ in ('top', 'right'):
        ax.spines[s_].set_visible(False)
from matplotlib.patches import Patch
ley = [Patch(color=C['experto'], label='Experto (a)'), Patch(color=C['vla40k'], label='SmolVLA 40k (a)'),
       Patch(color=C['vlapo40k'], label='SmolVLA pinza = orden (a)'), Patch(color='#8a8984', label='Sin ruido (b)'),
       Patch(color='#2a78d6', label='Ruido ±3 mm, ±10° (b)')]
fig.legend(handles=ley, loc='lower center', ncol=5, frameon=False, fontsize=6.4, bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(rect=(0, 0.08, 1, 1))
fig.savefig(os.path.join(FIG, 'fig_v2_posicion_margen_v9.png'), dpi=220, bbox_inches='tight')
print('res_v9.json y fig_v2_posicion_margen_v9.png escritos;',
      {k: v for k, v in RES.items() if k.startswith(('na', 'pos_', 'bar_')) and not k.endswith('tabla')})

# ------------------------------------------------------------------ copias _v9 más bajas de tres figuras grandes (mismo contenido; solo se recorta
# el margen blanco y se rellena a los lados para que, con el ancho fijo que les da build_tecnia, ocupen menos alto; las de relación 0 solo
# se copian: con otro nombre build_tecnia las pone al 84 % del ancho en vez de al 100 %)
from PIL import Image, ImageOps
for nom, asp in (('fig_camara', 1.40), ('fig_diff', 1.40), ('fig_v2_arquitectura', 2.5), ('fig_loc_plan', 0), ('fig_ctrl', 0), ('fig_vla', 0)):
    im = Image.open(os.path.join(FIG, nom + '.png')).convert('RGB')
    im = im.crop(ImageOps.invert(im).getbbox())
    w, h = im.size; W = max(w, int(round(h * asp)))
    lienzo = Image.new('RGB', (W, h), 'white'); lienzo.paste(im, ((W - w) // 2, 0))
    lienzo.save(os.path.join(FIG, nom + '_v9.png'))
