#!/usr/bin/env python3
"""Resultados para el paper v10 (reescritura SO-101 con la revisión de los asesores, 15-nov-2026).
1) Reutiliza TODO el cálculo de la v9 ejecutando resultados_v9.py hasta antes de escribir res_v9.json (no escribe nada de la v9:
   ni res_v9.json ni sus figuras).
2) Añade lo que pide la revisión de los asesores:
   - análisis PAREADO de las misiones experto / SmolVLA 40k (y pinza reetiquetada) en las semillas comunes 21-24: cada misión i de una
     semilla tiene el mismo color pedido y el mismo orden de cubos con ambas políticas (se comprueba); McNemar exacto (principal) y mid-p
     (sensibilidad) [comentarios 42 y 51];
   - fallos de navegación pareados en esas mismas misiones;
   - duración (media ± desviación típica, solo misiones completas) y distancia final del cubo al centro del plato, con su denominador [52];
   - error de percepción de la primera detección (columna err_est1_mm) del banco de las tres estrategias clásicas
     (agarre_so101_lote5_n10_semilla11.csv: 10 posiciones × 3 estrategias) [25];
   - IC de Wilson de 0/18 y 0/21 por separado [54]; porcentajes exactos con dos decimales.
3) Escribe res_v10.json (no genera figuras: la v10 usa fig_v2_resultados_v8.png, fig_v2_posicion_margen_v9.png y
   fig_v2_arquitectura_v10.png, esta última con hacer_figs_v2_v10.py).
Uso: python resultados_v10.py"""
import csv, json, math, os, statistics, sys

G = os.path.dirname(os.path.abspath(__file__))
D14 = os.path.join(G, '..', 'datos', '14nov')
DV2 = os.path.join(G, '..', 'datos', '11-12nov')

src = open(os.path.join(G, 'resultados_v9.py'), encoding='utf-8').read()
corte = src.index("json.dump(RES, open(os.path.join(G, 'salidas', 'res_v9.json')")
ns = {'__file__': os.path.join(G, 'resultados_v9.py'), '__name__': 'resultados_v9_parcial'}
_argv = sys.argv; sys.argv = [sys.argv[0]]
exec(compile(src[:corte], 'resultados_v9.py', 'exec'), ns)
sys.argv = _argv
RES, leer, wilson, ic, mcnemar, EST = (ns[k] for k in ('RES', 'leer', 'wilson', 'ic', 'mcnemar', 'EST'))


def ic1(s, n):
    lo, hi = wilson(s, n); return f'{100 * lo:.1f}-{100 * hi:.1f} %'


def sci(x):
    m, e = f'{x:.1e}'.split('e'); return f'{m}·10^{int(e)}', f'{m}\\cdot10^{{{int(e)}}}'


# ------------------------------------------------------------------ misiones pareadas (semillas 21-24)
SEM = [21, 22, 23, 24]


def tanda(pol, s):
    return leer(os.path.join(D14, f'final_misiones_{pol}_A7e2_n20_s{s}.csv'))


for pol, clave in (('vla40k', 'pm'), ('vlapo40k', 'pmpo')):
    b = c = n = 0; nb = nc = 0
    for s in SEM:
        E, V = tanda('experto', s), tanda(pol, s)
        assert len(E) == len(V) == 20, (pol, s)
        for e, v in zip(E, V):
            assert (e['mision'], e['color'], e['orden_cubos']) == (v['mision'], v['color'], v['orden_cubos']), (pol, s, e['mision'])
            xe, xv = int(e['exito'] or 0), int(v['exito'] or 0)
            n += 1; b += xe and not xv; c += xv and not xe
            fe = e['etapa_fallo'] in ('nav_recojo', 'nav_entrega'); fv = v['etapa_fallo'] in ('nav_recojo', 'nav_entrega')
            nb += fe and not fv; nc += fv and not fe
    ex, mp = mcnemar(b, c); exn, mpn = mcnemar(nb, nc)
    RES.update({f'{clave}_n': n, f'{clave}_b': b, f'{clave}_c': c, f'{clave}_pex': sci(ex)[0], f'{clave}_pmid': sci(mp)[0],
                f'{clave}_pex_f': f'{ex:.4f}', f'{clave}_pmid_f': f'{mp:.4f}',
                f'{clave}_navb': nb, f'{clave}_navc': nc, f'{clave}_navpex': f'{exn:.3f}', f'{clave}_navpmid': f'{mpn:.3f}'})
# éxitos de cada política en esas 80 misiones
RES['pm_e_ok'] = sum(int(r['exito'] or 0) for s in SEM for r in tanda('experto', s))
RES['pm_v_ok'] = sum(int(r['exito'] or 0) for s in SEM for r in tanda('vla40k', s))

# ------------------------------------------------------------------ duración y error en el plato (misiones completas)
import glob
for pol, clave in (('experto', 'e'), ('vla40k', 'v'), ('vlapo40k', 'po')):
    rows = [r for f in sorted(glob.glob(os.path.join(D14, f'final_misiones_{pol}_A7e2_n20_s*.csv'))) for r in leer(f)]
    ok = [r for r in rows if int(r['exito'] or 0)]
    t = [float(r['total_s']) for r in ok]; e = [float(r['cubo_err_plato_mm']) / 10 for r in ok]
    RES.update({f'dur_{clave}': f'{statistics.mean(t):.0f} ± {statistics.stdev(t):.0f}', f'dur_{clave}_n': len(t),
                f'plato_{clave}': f'{statistics.mean(e):.1f} ± {statistics.stdev(e):.1f}', f'n_{clave}': len(rows), f'ok_{clave}': len(ok)})
    RES[f'pctx_{clave}'] = f'{100 * len(ok) / len(rows):.2f}'.rstrip('0').rstrip('.')

# ------------------------------------------------------------------ error de percepción (primera detección, banco de 10 posiciones)
P = leer(os.path.join(DV2, 'agarre_so101_lote5_n10_semilla11.csv'))
err = [float(r['err_est1_mm']) for r in P if r['err_est1_mm']]
# definición (so101_trial.py): distancia en el plano entre el centro estimado en la primera detección y la posición real del cubo dada por
# Gazebo, ambas en base_footprint en ese instante. cubo_x/cubo_y del CSV son la colocación pedida, no la pose real en ese instante,
# por eso no sirven para recalcular el error.
RES.update(perc_n=len(err), perc_pos=len({(r['cubo_x'], r['cubo_y']) for r in P}), perc_media=f'{statistics.mean(err):.2f}',
           perc_de=f'{statistics.stdev(err):.2f}', perc_min=f'{min(err):.1f}', perc_max=f'{max(err):.1f}')
for est, k in (('ik_directa', 'dir'), ('multietapa', 'eta'), ('servovisual', 'sv')):
    RES[f'clas_{k}'] = f"{sum(int(r['exito']) for r in P if r['estrategia'] == est)}/{sum(1 for r in P if r['estrategia'] == est)}"

# ------------------------------------------------------------------ extremo derecho por separado
RES['ic_d_v'] = ic1(*map(int, RES['pos_vla40k_d'].split('/')))
RES['ic_d_po'] = ic1(*map(int, RES['pos_vlapo40k_d'].split('/')))

json.dump(RES, open(os.path.join(G, 'salidas', 'res_v10.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('res_v10.json escrito;', {k: v for k, v in RES.items() if k.startswith(('pm', 'dur', 'plato', 'perc', 'clas', 'ic_d', 'pctx', 'n_', 'ok_'))})
