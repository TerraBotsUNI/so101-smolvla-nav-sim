#!/bin/bash
# 14-nov (h), VM con 40 vCPU / 40 GB: 4 simulaciones a la vez con el PAQUETE PRINCIPAL (ya con A7e2; sin configuración superpuesta).
#  S1 (dom 87, puerto 5555): termina la reevaluación del brazo (50 escenas) -> VLA s26 -> VLA s27
#  S2 (dom 85, puerto 5556): reanuda VLA s25 -> VLA s28
#  S3 (dom 88): reanuda experto s26 -> experto s27 -> experto s28
#  S4 (dom 89): experto s29 -> experto s30
# Los nombres de archivo siguen con A7e2 (misma configuración). Resumen con IC en RESUMEN_NOCHE14.txt al terminar cada tanda.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE14.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
resumen() { /usr/bin/python3 $V/resumen_noche14.py > $R/RESUMEN_NOCHE14.txt 2>&1; }
C=A7e2; M=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
vla() { VIDEO=$V/videos_mision/vla40k_${C}_s$1 VLA_PUERTO=$4 bash $V/mision_overlay2.sh vla $M 20 $1 $R/final_misiones_vla40k_${C}_n20_s$1.csv $V/intentos_mision/final_vla40k_${C}_s$1 $R/dia14h_vla_s$1.log $2 $3
  estado "VLA 40k ($C) semilla $1: $(exito $R/final_misiones_vla40k_${C}_n20_s$1.csv)/20"; resumen; }
exp() { VIDEO=$V/videos_mision/experto_${C}_s$1 bash $V/mision_overlay2.sh ik_directa - 20 $1 $R/final_misiones_experto_${C}_n20_s$1.csv $V/intentos_mision/final_experto_${C}_s$1 $R/dia14h_experto_s$1.log $2 $3
  estado "experto ($C) semilla $1: $(exito $R/final_misiones_experto_${C}_n20_s$1.csv)/20"; resumen; }
bash $V/monitor_recursos.sh $R/consumo_dia14h.csv & MON=$!
trap 'kill $MON 2>/dev/null' EXIT
estado "(h) VM con $(nproc) vCPU y $(free -g | awk '/Mem/{print $2}') GB: 4 simulaciones con el paquete principal (A7e2)"
( VLA_PUERTO=5555 bash $V/evaluar_overlay.sh $M 50 vla,ik_directa $R/eval_brazo_A7e2_40k_n50_s900.csv $V/intentos_vla_escena/eval_A7e2_40k $R/dia14h_eval_brazo.log 87 so101_foto
  estado "brazo 2 N·m (50 escenas): $(tail -n +2 $R/eval_brazo_A7e2_40k_n50_s900.csv | awk -F, '$4=="vla"{v+=$5;nv++} $4=="ik_directa"{e+=$5;ne++} END {print "VLA " v+0 "/" nv+0 ", experto " e+0 "/" ne+0}')"; resumen
  vla 26 87 so101_foto 5555; vla 27 87 so101_foto 5555 ) & P1=$!
sleep 30; ( vla 25 85 so101_prueba 5556; vla 28 85 so101_prueba 5556 ) & P2=$!
sleep 30; ( exp 26 88 so101_mision; exp 27 88 so101_mision; exp 28 88 so101_mision ) & P3=$!
sleep 30; ( exp 29 89 so101_d89; exp 30 89 so101_d89 ) & P4=$!
wait $P1 $P2 $P3 $P4
resumen; estado "FIN (h); resumen en RESUMEN_NOCHE14.txt"
