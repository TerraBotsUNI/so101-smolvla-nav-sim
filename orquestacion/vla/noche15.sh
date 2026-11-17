#!/bin/bash
# 15-nov noche: misiones finales, sin entrenamiento en la GPU y con 2 simulaciones (regla de carga).
# Espera a que terminen la evaluación del VLA v2 (paso2_4.sh) y la de ACT (tarde15_act.sh).
#  S1 (dom 87): experto MARGEN 26 mm s21, s22  → VLA v2 s23, s24
#  S2 (dom 88): experto MARGEN 26 mm s23, s24  → VLA v2 s21, s22
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE15.txt; cd $D
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
aviso() { grep -c "missed its desired rate" /tmp/so101_mision_$1_launch.log 2>/dev/null || echo 0; }
until grep -q "FIN pasos 2-4" $R/ESTADO_PASO2.txt 2>/dev/null && grep -q "FIN evaluación ACT" $R/ESTADO_ACT.txt 2>/dev/null; do sleep 120; done
MV2=$V/entrenos/smolvla_v2_mision_30k/checkpoints/030000/pretrained_model
estado "INICIO misiones finales: experto 26 mm y VLA v2, semillas 21-24, 2 simulaciones sin entrenamiento"
exp26() { SO101_MARGEN=0.026 VIDEO=$V/videos_mision/experto_m26_s$1 bash $V/mision_overlay2.sh ik_directa - 20 $1 $R/final_misiones_experto_m26_A7e2_n20_s$1.csv $V/intentos_mision/final_experto_m26_s$1 $R/noche15_experto_m26_s$1.log $2 $3
  estado "experto 26 mm semilla $1: $(exito $R/final_misiones_experto_m26_A7e2_n20_s$1.csv)/20; avisos Nav2: $(aviso $2)"; }
vv2() { VIDEO=$V/videos_mision/vlav2_s$1 VLA_PUERTO=$4 bash $V/mision_overlay2.sh vla $MV2 20 $1 $R/final_misiones_vlav2_A7e2_n20_s$1.csv $V/intentos_mision/final_vlav2_s$1 $R/noche15_vlav2_s$1.log $2 $3
  estado "VLA v2 semilla $1: $(exito $R/final_misiones_vlav2_A7e2_n20_s$1.csv)/20; avisos Nav2: $(aviso $2)"; }
( exp26 21 87 so101_foto; exp26 22 87 so101_foto; [ -d $MV2 ] && { vv2 23 87 so101_foto 5555; vv2 24 87 so101_foto 5555; } ) &
sleep 90
( exp26 23 88 so101_mision; exp26 24 88 so101_mision; [ -d $MV2 ] && { vv2 21 88 so101_mision 5556; vv2 22 88 so101_mision 5556; } ) &
wait; estado "FIN noche15"
