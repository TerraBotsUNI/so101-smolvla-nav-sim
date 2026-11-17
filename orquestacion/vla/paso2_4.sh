#!/bin/bash
# 15-nov, pasos 2-4 del plan (diagnóstico de fallos), encadenados tras el barrido del paso 1 (paso1_margen.sh):
#  2) Dataset v2: 2 colectores x 300 episodios con la disposición de MISIÓN (pedido a la izquierda, al centro o a la derecha), el MARGEN elegido
#     en el paso 1 y la pinza a 2 N·m (URDF actual). Semillas nuevas. No se mezcla con las 457 demostraciones antiguas.
#  3) Conversión (acción = estado siguiente, sin reetiquetar: el reetiquetado no mejoró) y ajuste SmolVLA 30k pasos, lote 32 (sin simulaciones).
#  4) Evaluación, 2 simulaciones: S1 banco con disposición de demostración, semilla 900 (50 escenas, VLA v2 + experto con el margen nuevo);
#     S2 banco con disposición de misión, semilla 910 (50 escenas, VLA v2 + experto con el margen nuevo).
# Criterio del margen (fijado ANTES de ver el barrido): el de mayor éxito con ruido (±3 mm, ±10°); a igualdad, el de mayor éxito sin ruido; a
# igualdad, el menor. Se descarta un margen cuyo éxito sin ruido sea 2 o más escenas peor que el de 18 mm.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_PASO2.txt; cd $D
export HF_HOME=$D/hf_cache PYTHONIOENCODING=utf-8
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, -v e="${2:-}" '(e=="" || $4==e){s+=$5;n++} END {print s+0 "/" n+0}'; }
until grep -q "FIN paso 1" $R/ESTADO_PASO1.txt 2>/dev/null; do sleep 120; done
M=$(/usr/bin/python3 - <<'P'
import csv, os
R = os.path.join(os.environ.get('PROYECTO', os.path.expanduser('~/proyecto/paper_rover_vla_2025')), 'vla', 'registros')
def ok(m, r):
    f = f'{R}/paso1_experto_m{m}_r{r}_mision_s910.csv'
    return sum(int(x['exito'] or 0) for x in csv.DictReader(open(f))) if os.path.exists(f) else -1
base = ok(18, 0)
cand = [(ok(m, 3), ok(m, 0), -m, m) for m in (18, 22, 26, 30) if ok(m, 0) >= base - 1]
print(max(cand)[3] if cand else 18)
P
)
estado "INICIO pasos 2-4: margen elegido $M mm (criterio fijado antes del barrido; ver paso1_experto_m*_mision_s910.csv)"
A=$D/demos/crudas_v2_a; B=$D/demos/crudas_v2_b; mkdir -p $A $B
cuantos() { ls -d $1/ep_* 2>/dev/null | wc -l; }
colector_resiliente() {   # dominio particion carpeta objetivo semilla_base registro
  local DOM=$1 PART=$2 OUT=$3 N=$4 SB=$5 LOG=$6 k=0
  while [ $(cuantos $OUT) -lt $N ] && [ $k -lt 12 ]; do
    local falta=$(( N - $(cuantos $OUT) ))
    SO101_DISPOSICION=mision SO101_MARGEN=0.0$M bash $V/colector.sh $DOM $PART $OUT $falta $((SB + 10 * k)) $LOG; sleep 10; k=$((k + 1))
  done
  estado "colector $DOM terminado: $(cuantos $OUT) episodios en $OUT"
}
colector_resiliente 87 so101_foto $A 300 5100 $R/paso2_demos_a.log &
sleep 60
colector_resiliente 88 so101_mision $B 300 6200 $R/paso2_demos_b.log &
wait
NOK=$(grep -l '"exito": true' $A/ep_*/meta.json $B/ep_*/meta.json 2>/dev/null | wc -l)
estado "paso 2 terminado: $(( $(cuantos $A) + $(cuantos $B) )) episodios, $NOK exitosos"
DS=$D/demos/lerobot_v2_mision; SAL=$V/entrenos/smolvla_v2_mision_30k; MV2=$SAL/checkpoints/030000/pretrained_model
env/bin/python $V/convertir_demos_lerobot.py --crudas $A $B --salida $DS > $R/paso3_convertir.log 2>&1
estado "dataset v2: $(tail -1 $R/paso3_convertir.log)"
CAM2=scene bash $V/entrenar.sh $DS local/so101_v2_mision $SAL 30000 32 $R/paso3_entreno.log
estado "ajuste v2 30k terminado (código $?)"
[ -d $MV2 ] || { estado "ERROR: no hay modelo en $MV2"; exit 1; }
( SO101_MARGEN=0.0$M SO101_DISPOSICION=demo SEMILLA=900 VLA_PUERTO=5555 bash $V/evaluar_semilla.sh $MV2 50 vla,ik_directa $R/eval_brazo_v2_demo_s900.csv $V/intentos_vla_escena/eval_v2_demo_s900 $R/paso4_demo_s900.log 87 so101_foto
  estado "banco demo s900: VLA v2 $(exito $R/eval_brazo_v2_demo_s900.csv vla), experto (margen $M) $(exito $R/eval_brazo_v2_demo_s900.csv ik_directa) [antes VLA 40k 36/50, experto 44/50]" ) &
sleep 60
( SO101_MARGEN=0.0$M SO101_DISPOSICION=mision SEMILLA=910 VLA_PUERTO=5556 bash $V/evaluar_semilla.sh $MV2 50 vla,ik_directa $R/eval_brazo_v2_mision_s910.csv $V/intentos_vla_escena/eval_v2_mision_s910 $R/paso4_mision_s910.log 88 so101_mision
  estado "banco misión s910: VLA v2 $(exito $R/eval_brazo_v2_mision_s910.csv vla), experto (margen $M) $(exito $R/eval_brazo_v2_mision_s910.csv ik_directa)" ) &
wait
# referencia: el VLA 40k anterior en el mismo banco con disposición de misión (para medir cuánto mejora el v2 en las mismas escenas)
M40=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
SO101_DISPOSICION=mision SEMILLA=910 VLA_PUERTO=5555 bash $V/evaluar_semilla.sh $M40 50 vla $R/eval_brazo_40k_mision_s910.csv $V/intentos_vla_escena/eval_40k_mision_s910 $R/paso4_40k_mision_s910.log 87 so101_foto
estado "banco misión s910: VLA 40k anterior $(exito $R/eval_brazo_40k_mision_s910.csv vla)"
estado "FIN pasos 2-4"
