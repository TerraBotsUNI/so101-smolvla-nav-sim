#!/usr/bin/python3
"""Resumen de las misiones y evaluaciones del 14-nov con IC 95 % de Wilson. Uso: python3 resumen_noche14.py > RESUMEN_NOCHE14.txt"""
import csv, glob, math, os, collections
R = os.path.join(os.environ.get('PROYECTO', os.path.expanduser('~/proyecto/paper_rover_vla_2025')), 'vla', 'registros')
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))
print('RESUMEN 14-nov (A7e2 = pinza 2 N·m + acercamiento fino con AMCL en la entrega)\n')
for est in ('experto', 'vla40k'):
    tot = [0, 0]; etapas = collections.Counter()
    for f in sorted(glob.glob(f'{R}/final_misiones_{est}_A7e2_n20_s*.csv')):
        filas = list(csv.DictReader(open(f))); k = sum(int(r['exito'] or 0) for r in filas)
        etapas.update(r['etapa_fallo'] for r in filas if r['etapa_fallo'])
        tot[0] += k; tot[1] += len(filas); print(f'  {os.path.basename(f)}: {k}/{len(filas)}')
    lo, hi = wilson(*tot)
    print(f'MISIONES {est}: {tot[0]}/{tot[1]} = {100 * tot[0] / max(1, tot[1]):.0f} % (IC 95 % {lo:.0f}-{hi:.0f} %); fallos por etapa: {dict(etapas)}\n')
for f in sorted(glob.glob(f'{R}/eval_brazo_A7e2_*.csv')):
    filas = list(csv.DictReader(open(f))); c = collections.defaultdict(lambda: [0, 0])
    for r in filas:
        c[r['estrategia']][0] += int(r['exito'] or 0); c[r['estrategia']][1] += 1
    print(f'BRAZO {os.path.basename(f)}: ' + ', '.join(f'{e} {k}/{n} ({100 * k / max(1, n):.0f} %)' for e, (k, n) in c.items()))
print('\nReferencias previas: misiones experto antes de la corrección 3/20 (12-nov), A4 0/20; brazo con 10 N·m: VLA 40k 36/50 (72 %), experto 40/50 (80 %).')
