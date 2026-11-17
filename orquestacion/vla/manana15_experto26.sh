#!/bin/bash
# 15-nov mañana: misiones del EXPERTO con el margen nuevo (26 mm), semillas 21-24 (las mismas de las tandas del VLA), 1 simulación
# (regla: 1 sola simulación mientras se entrena SmolVLA v2). Referencia justa para comparar con el VLA v2.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_MANANA15.txt; cd $D
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
aviso() { grep -c "missed its desired rate" /tmp/so101_mision_$1_launch.log 2>/dev/null || echo 0; }
for s in 21 22 23 24; do
  SO101_MARGEN=0.026 VIDEO=$V/videos_mision/experto_m26_s$s bash $V/mision_overlay2.sh ik_directa - 20 $s $R/final_misiones_experto_m26_A7e2_n20_s$s.csv $V/intentos_mision/final_experto_m26_s$s $R/manana15_experto_m26_s$s.log 89 so101_d89
  estado "experto MARGEN 26 mm semilla $s: $(exito $R/final_misiones_experto_m26_A7e2_n20_s$s.csv)/20; avisos Nav2: $(aviso 89)"
done
estado "FIN experto m26"
