#!/bin/bash
# Noche 14-nov (e): tanda VLA 40k con A7e2 DESPUÉS de la del experto (una sola simulación a la vez: con dos + otra simulación ajena la máquina
# se saturaba y Nav2 fallaba al ir al recojo). 20 misiones, semilla 21, dominio 87, vídeo continuo.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE14.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
while pgrep -f "bash vla/noche14d.sh" > /dev/null; do sleep 30; done
CFG=A7e2; M=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
bash $V/monitor_recursos.sh $R/consumo_noche14e.csv & MON=$!
trap 'kill $MON 2>/dev/null' EXIT
estado "(e) tanda VLA 40k con $CFG (20 misiones, semilla 21, vídeo), sola en la máquina"
OVERLAY=/tmp/so101_ws_$CFG/install VIDEO=$V/videos_mision/vla40k_$CFG bash $V/mision_overlay.sh vla $M 20 21 $R/final_misiones_vla40k_${CFG}_n20_s21.csv $V/intentos_mision/final_vla40k_$CFG $R/noche14e_vla.log 87 so101_foto
estado "tanda final VLA 40k ($CFG): $(exito $R/final_misiones_vla40k_${CFG}_n20_s21.csv)/20"
estado "FIN noche 14 (e)"
