#!/bin/bash
# Segundo orquestador de la noche del 12-nov (no toca a orquestador_escena.sh; se guía por su ESTADO_ESCENA.txt):
#   A) En cuanto terminan los colectores (la GPU queda para el ajuste definitivo y la CPU libre): 20 misiones completas con el EXPERTO
#      (semilla 21, como la tanda del paper v7) en el dominio 88 -> línea base pareada.
#   B) Cuando termina orquestador_escena.sh: se amplía la evaluación pareada del modelo definitivo de 20 a 50 escenas (dominio 85).
#   C) 20 misiones completas con el VLA definitivo haciendo el brazo (semilla 21, pareadas con A) en el dominio 88.
#   Al final, RESUMEN_NOCHE2.txt con los conteos. Estado en vla/registros/ESTADO_NOCHE2.txt.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE2.txt; F=$(date +%F)
estado() { echo "$(date '+%F %T') $*" >> $E; }
estado "ORQUESTADOR NOCHE 2: misiones experto (durante el ajuste) + evaluación a 50 escenas + misiones con VLA"
until grep -q "COLECTORES terminados" $R/ESTADO_ESCENA.txt; do sleep 60; done
estado "A) misiones con el experto (20, semilla 21, dominio 88)"
bash $V/mision.sh ik_directa - 20 21 $R/misiones_experto_n20_s21_$F.csv $V/intentos_mision/experto $R/noche2_misiones_experto.log 88 so101_mision
estado "A) terminado (código $?): $(tail -n +2 $R/misiones_experto_n20_s21_$F.csv 2>/dev/null | awk -F, '{s+=$5} END {print s"/"NR" éxitos"}')"

until grep -q "FIN orquestador escena" $R/ESTADO_ESCENA.txt; do sleep 60; done
DEF=$(ls -d $V/entrenos/smolvla_escena_definitivo_*/checkpoints/[0-9]*/pretrained_model 2>/dev/null | sort | tail -n 1)
if [ -z "$DEF" ]; then estado "no hay modelo definitivo: fin"; exit 1; fi
CSVE=$(ls $R/eval_escena_definitivo_n20_*.csv 2>/dev/null | tail -n 1); CSVE=${CSVE:-$R/eval_escena_definitivo_n20_$F.csv}
estado "B) evaluación pareada ampliada a 50 escenas: $DEF -> $CSVE"
bash $V/evaluar.sh $DEF 50 vla,ik_directa $CSVE $V/intentos_vla_escena/definitivo $R/noche2_eval50.log 85 so101_prueba
estado "B) terminado (código $?)"

estado "C) misiones con el VLA definitivo (20, semilla 21, dominio 88)"
bash $V/mision.sh vla $DEF 20 21 $R/misiones_vla_n20_s21_$F.csv $V/intentos_mision/vla $R/noche2_misiones_vla.log 88 so101_mision
estado "C) terminado (código $?)"

/usr/bin/python3 - $R $F > $R/RESUMEN_NOCHE2.txt <<'P'
import csv, glob, sys, collections
R, F = sys.argv[1], sys.argv[2]
for f in sorted(glob.glob(f'{R}/eval_escena_*.csv')):
    c = collections.defaultdict(lambda: [0, 0])
    for r in csv.DictReader(open(f)):
        c[r['estrategia']][0] += int(r['exito']); c[r['estrategia']][1] += 1
    print(f.split('/')[-1], {k: f'{a}/{b}' for k, (a, b) in c.items()})
for f in sorted(glob.glob(f'{R}/misiones_*_{F}.csv')):
    rs = list(csv.DictReader(open(f))); print(f.split('/')[-1], f"{sum(int(r['exito']) for r in rs)}/{len(rs)} misiones completas",
          dict(collections.Counter(r['etapa_fallo'] for r in rs if not int(r['exito']))))
P
estado "FIN orquestador noche 2 (ver RESUMEN_NOCHE2.txt)"
