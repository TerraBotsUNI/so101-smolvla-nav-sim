#!/bin/bash
# Noche 14-nov (f), VM ampliada a 32 vCPU: 3 simulaciones a la vez con A7e2 (pinza 2 N·m + acercamiento fino en la entrega), vídeo continuo.
#   P1: VLA 40k semilla 21 y luego semilla 22 (dominio 87; un solo servidor de política, puerto 5555)
#   P2: experto semilla 22 (dominio 85)      P3: experto semilla 23 (dominio 88)
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE14.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
for w in A2 A5 A6 A7e1 A7e2; do [ -d /tmp/so101_ws_$w ] || cp -a $D/respaldo_tmp_overlays/so101_ws_$w /tmp/; done
[ -f /tmp/so101_ws_A7e2/install/setup.bash ] || { estado "ERROR: no se pudo restaurar /tmp/so101_ws_A7e2"; exit 1; }
bash $V/monitor_recursos.sh $R/consumo_noche14f.csv & MON=$!
trap 'kill $MON 2>/dev/null' EXIT
C=A7e2; O=/tmp/so101_ws_$C/install; M=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
estado "(f) VM con $(nproc) vCPU: VLA 40k s21->s22 (dom 87) + experto s22 (dom 85) + experto s23 (dom 88), $C, con vídeo"
( for S in 21 22; do
    OVERLAY=$O VIDEO=$V/videos_mision/vla40k_${C}_s$S bash $V/mision_overlay.sh vla $M 20 $S $R/final_misiones_vla40k_${C}_n20_s$S.csv $V/intentos_mision/final_vla40k_${C}_s$S $R/noche14f_vla_s$S.log 87 so101_foto
    estado "VLA 40k ($C) semilla $S: $(exito $R/final_misiones_vla40k_${C}_n20_s$S.csv)/20"
  done ) & P1=$!
sleep 40
( OVERLAY=$O VIDEO=$V/videos_mision/experto_${C}_s22 bash $V/mision_overlay.sh ik_directa - 20 22 $R/final_misiones_experto_${C}_n20_s22.csv $V/intentos_mision/final_experto_${C}_s22 $R/noche14f_experto_s22.log 85 so101_prueba
  estado "experto ($C) semilla 22: $(exito $R/final_misiones_experto_${C}_n20_s22.csv)/20" ) & P2=$!
sleep 40
( OVERLAY=$O VIDEO=$V/videos_mision/experto_${C}_s23 bash $V/mision_overlay.sh ik_directa - 20 23 $R/final_misiones_experto_${C}_n20_s23.csv $V/intentos_mision/final_experto_${C}_s23 $R/noche14f_experto_s23.log 88 so101_mision
  estado "experto ($C) semilla 23: $(exito $R/final_misiones_experto_${C}_n20_s23.csv)/20" ) & P3=$!
wait $P1 $P2 $P3
estado "FIN noche 14 (f)"
