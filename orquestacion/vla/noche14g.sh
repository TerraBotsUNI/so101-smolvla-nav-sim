#!/bin/bash
# Plan de 8 h (14-nov, 04:00-12:00), además de noche14f (VLA s21->s22 en dom 87; experto s22 y s23 en dom 85/88):
#  1) cuando terminen los expertos s22/s23: VLA 40k s23 -> s24 (dom 85, servidor en puerto 5556) y experto s24 -> s25 (dom 88)
#  2) cuando termine noche14f: reevaluación del brazo con la pinza a 2 N·m, 50 escenas pareadas (semilla 900, las mismas que con 10 N·m),
#     VLA 40k + experto (dom 87, puerto 5555)
#  3) si queda tiempo antes de las 11:00: VLA s25 (dom 85) y experto s26 (dom 88)
#  Al final: vla/registros/RESUMEN_NOCHE14.txt con IC de Wilson.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE14.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
C=A7e2; O=/tmp/so101_ws_$C/install; M=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
vla() {   # vla <semilla> <dominio> <particion> <puerto>
  OVERLAY=$O VIDEO=$V/videos_mision/vla40k_${C}_s$1 VLA_PUERTO=$4 bash $V/mision_overlay2.sh vla $M 20 $1 $R/final_misiones_vla40k_${C}_n20_s$1.csv $V/intentos_mision/final_vla40k_${C}_s$1 $R/noche14g_vla_s$1.log $2 $3
  estado "VLA 40k ($C) semilla $1: $(exito $R/final_misiones_vla40k_${C}_n20_s$1.csv)/20"; }
exp() {   # exp <semilla> <dominio> <particion>
  OVERLAY=$O VIDEO=$V/videos_mision/experto_${C}_s$1 bash $V/mision_overlay2.sh ik_directa - 20 $1 $R/final_misiones_experto_${C}_n20_s$1.csv $V/intentos_mision/final_experto_${C}_s$1 $R/noche14g_experto_s$1.log $2 $3
  estado "experto ($C) semilla $1: $(exito $R/final_misiones_experto_${C}_n20_s$1.csv)/20"; }
antes_de() { [ $(date +%H%M | sed 's/^0*//') -lt $1 ]; }
estado "(g) plan de 8 h en cola"
while pgrep -f "mision_overlay.sh ik_directa - 20 2[23] " > /dev/null; do sleep 60; done
( vla 23 85 so101_prueba 5556; antes_de 900 && vla 24 85 so101_prueba 5556; antes_de 1000 && vla 25 85 so101_prueba 5556 ) & P1=$!
( exp 24 88 so101_mision; antes_de 900 && exp 25 88 so101_mision; antes_de 1000 && exp 26 88 so101_mision ) & P2=$!
while pgrep -f "bash vla/noche14f.sh" > /dev/null; do sleep 60; done
estado "reevaluación del brazo con pinza 2 N·m: 50 escenas pareadas (semilla 900), VLA 40k + experto"
OVERLAY=$O VLA_PUERTO=5555 bash $V/evaluar_overlay.sh $M 50 vla,ik_directa $R/eval_brazo_A7e2_40k_n50_s900.csv $V/intentos_vla_escena/eval_A7e2_40k $R/noche14g_eval_brazo.log 87 so101_foto
estado "brazo 2 N·m: $(tail -n +2 $R/eval_brazo_A7e2_40k_n50_s900.csv | awk -F, '$4=="vla"{v+=$5;nv++} $4=="ik_directa"{e+=$5;ne++} END {print "VLA " v+0 "/" nv+0 ", experto " e+0 "/" ne+0}')"
wait $P1 $P2
/usr/bin/python3 $V/resumen_noche14.py > $R/RESUMEN_NOCHE14.txt 2>&1
estado "FIN noche 14 (g); resumen en RESUMEN_NOCHE14.txt"
