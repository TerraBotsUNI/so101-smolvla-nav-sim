# Resumen de la ablación de cobertura: éxito del VLA por posición del cubo pedido (izquierda / centro / derecha) en el banco s910
# (disposición de misión) y total en s900 (disposición de las demostraciones), frente a SmolVLA 40k, ACT y SmolVLA v2 en las MISMAS escenas.
# Solo biblioteca estándar (se corre con /usr/bin/python3). Uso: python3 resumen_ablacion.py <carpeta_registros>
import csv, math, os, sys
R = sys.argv[1]
POS = ('izquierda', 'centro', 'derecha')


def leer(f):
    p = os.path.join(R, f)
    if not os.path.exists(p): return None
    out = {}
    for r in csv.DictReader(open(p)):
        if r['estrategia'] != 'vla': continue
        cub = {}
        for it in r['cubos'].split(';'):
            c, v = it.split(':'); cub[c] = [float(x) for x in v.split(',')]
        y = cub[r['color']][1]; o = [v[1] for c, v in cub.items() if c != r['color']]
        pos = 2 if all(v > y for v in o) else (0 if all(v < y for v in o) else 1)   # y positiva = izquierda del robot
        out[int(r['escena'])] = (pos, int(r['exito'] or 0))
    return out


def mcnemar_exacto(a, b):
    """a, b: dict escena -> éxito; p bilateral exacto (binomial) sobre los pares discordantes."""
    comunes = sorted(set(a) & set(b)); n01 = sum(1 for k in comunes if a[k] == 0 and b[k] == 1); n10 = sum(1 for k in comunes if a[k] == 1 and b[k] == 0)
    n = n01 + n10
    if n == 0: return n01, n10, 1.0
    k = min(n01, n10); p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return n01, n10, min(1.0, 2 * p)


def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'), float('nan'))
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0, c - h), 100 * min(1, c + h))


S910 = {'cob18': 'eval_brazo_cob18_mision_s910.csv', '40k': 'eval_brazo_40k_mision_s910.csv', 'ACT': 'eval_brazo_act_mision_s910.csv',
        'v2': 'eval_brazo_v2_mision_s910.csv'}
S900 = {'cob18': 'eval_brazo_cob18_demo_s900.csv', '40k': 'eval_brazo_A7e2_40k_n50_s900.csv', 'ACT': 'eval_brazo_act_demo_s900.csv',
        'v2': 'eval_brazo_v2_demo_s900.csv'}
print('Éxito del VLA por posición del cubo pedido (primer y único intento; pinza 2 N·m en la evaluación)')
D910 = {k: leer(f) for k, f in S910.items()}
for k, d in D910.items():
    if d is None: print(f's910 {k}: sin datos'); continue
    partes = []
    for p in range(3):
        v = [e for (q, e) in d.values() if q == p]; lo, hi = wilson(sum(v), len(v))
        partes.append(f'{POS[p]} {sum(v)}/{len(v)} (IC95 {lo:.0f}-{hi:.0f} %)')
    tot = [e for (_, e) in d.values()]
    print(f's910 {k}: ' + '; '.join(partes) + f'; total {sum(tot)}/{len(tot)}')
if D910['cob18']:
    for ref in ('40k', 'v2'):
        if not D910[ref]: continue
        a = {s: e for s, (_, e) in D910[ref].items()}; b = {s: e for s, (_, e) in D910['cob18'].items()}
        n01, n10, p = mcnemar_exacto(a, b)
        ad = {s: e for s, (q, e) in D910[ref].items() if q == 2}; bd = {s: e for s, (q, e) in D910['cob18'].items() if q == 2}
        m01, m10, pd_ = mcnemar_exacto(ad, bd)
        print(f'  McNemar exacto s910 cob18 frente a {ref}: total {n01} escenas solo cob18 / {n10} solo {ref}, p = {p:.3g}; '
              f'extremo derecho {m01}/{m10}, p = {pd_:.3g}')
for k, f in S900.items():
    d = leer(f)
    if d is None: print(f's900 {k}: sin datos'); continue
    tot = [e for (_, e) in d.values()]; lo, hi = wilson(sum(tot), len(tot))
    print(f's900 {k}: {sum(tot)}/{len(tot)} (IC95 {lo:.0f}-{hi:.0f} %)')
print('Lectura: si cob18 recupera el extremo derecho en s910 (como v2), la causa del 0/18 es la cobertura de los datos; si sigue fallando a la '
      'derecha, también importa la receta (margen 26 mm / pinza 2 N·m al grabar).')
