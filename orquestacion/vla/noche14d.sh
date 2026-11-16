#!/bin/bash
# Noche 14-nov (d): al terminar el banco de la pinza (noche14c), tandas finales grabadas con A7e2 = A5 (acercamiento fino con AMCL en la entrega)
# + límite de esfuerzo de la pinza 2.0 N·m (problema 31): 20 misiones experto (dominio 85) y 20 VLA 40k (dominio 87), semilla 21, vídeo continuo.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE14.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
while pgrep -f "bash vla/noche14c.sh" > /dev/null; do sleep 30; done
CFG=${CFG:-A7e2}; [ -f $V/CFG_NOCHE14D ] && CFG=$(cat $V/CFG_NOCHE14D)
bash $V/monitor_recursos.sh $R/consumo_noche14d.csv & MON=$!
trap 'kill $MON 2>/dev/null' EXIT
M=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
estado "(d) tandas finales con $CFG: 20 experto + 20 VLA 40k, semilla 21, con vídeo"
OVERLAY=/tmp/so101_ws_$CFG/install VIDEO=$V/videos_mision/experto_$CFG bash $V/mision_overlay.sh ik_directa - 20 21 $R/final_misiones_experto_${CFG}_n20_s21.csv $V/intentos_mision/final_experto_$CFG $R/noche14d_experto.log 85 so101_prueba & P1=$!
OVERLAY=/tmp/so101_ws_$CFG/install VIDEO=$V/videos_mision/vla40k_$CFG bash $V/mision_overlay.sh vla $M 20 21 $R/final_misiones_vla40k_${CFG}_n20_s21.csv $V/intentos_mision/final_vla40k_$CFG $R/noche14d_vla.log 87 so101_foto & P2=$!
wait $P1 $P2
estado "tanda final ($CFG): experto $(exito $R/final_misiones_experto_${CFG}_n20_s21.csv)/20, VLA 40k $(exito $R/final_misiones_vla40k_${CFG}_n20_s21.csv)/20"
estado "FIN noche 14"
