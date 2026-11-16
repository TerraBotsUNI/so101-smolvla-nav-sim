#!/bin/bash
# Noche 14-nov (b): tandas finales grabadas con A5 (A2 + acercamiento fino con AMCL en la entrega): 20 misiones experto (dominio 85)
# y 20 VLA 40k (dominio 87), semilla 21, vídeo continuo. Estado en vla/registros/ESTADO_NOCHE14.txt.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE14.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
bash $V/monitor_recursos.sh $R/consumo_noche14b.csv & MON=$!
trap 'kill $MON 2>/dev/null' EXIT
CFG=A5; M=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
estado "(b) comparación A5/A6 detenida a las 01:10 (A5 0/2, A6 2/4; la relocalización no corrige). Tanda final con $CFG: 20 experto + 20 VLA 40k, semilla 21, con vídeo"
OVERLAY=/tmp/so101_ws_$CFG/install VIDEO=$V/videos_mision/experto_$CFG bash $V/mision_overlay.sh ik_directa - 20 21 $R/final_misiones_experto_${CFG}_n20_s21.csv $V/intentos_mision/final_experto_$CFG $R/noche14_final_experto.log 85 so101_prueba & P1=$!
OVERLAY=/tmp/so101_ws_$CFG/install VIDEO=$V/videos_mision/vla40k_$CFG bash $V/mision_overlay.sh vla $M 20 21 $R/final_misiones_vla40k_${CFG}_n20_s21.csv $V/intentos_mision/final_vla40k_$CFG $R/noche14_final_vla.log 87 so101_foto & P2=$!
wait $P1 $P2
estado "tanda final ($CFG): experto $(exito $R/final_misiones_experto_${CFG}_n20_s21.csv)/20, VLA 40k $(exito $R/final_misiones_vla40k_${CFG}_n20_s21.csv)/20"
estado "FIN noche 14"
