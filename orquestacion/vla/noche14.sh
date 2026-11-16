#!/bin/bash
# Noche 14-nov. Configuraciones (todas parten de A2 = AMCL alpha1 0.4, recovery 0.1, tolerancias 0.12 m / 0.3 rad):
#   A5 = A2 + acercamiento fino en la entrega con la pose de AMCL (so101_mision.py afinar())
#   A6 = A5 + relocalización local de AMCL antes de afinar (reabre la nube y request_nomotion_update)
# 1) comparación pareada A5 vs A6: 20 misiones del experto cada una (semillas 21 y 22, mismas escenas), 2 simulaciones a la vez;
# 2) elige la mejor; 3) tanda final grabada con ella: 20 misiones experto + 20 VLA 40k (semilla 21), con vídeo continuo.
# Estado en vla/registros/ESTADO_NOCHE14.txt. (Corrige el fallo de tarde13.sh: `wait` sin argumentos esperaba también al monitor y se colgaba.)
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE14.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
bash $V/monitor_recursos.sh $R/consumo_noche14.csv & MON=$!
trap 'kill $MON 2>/dev/null' EXIT
for C in A5 A6; do
  [ -f /tmp/so101_ws_$C/install/setup.bash ] || { estado "ERROR: falta /tmp/so101_ws_$C compilado"; exit 1; }
  estado "$C: $(grep -c 'def afinar\|def relocal_local' /tmp/so101_ws_$C/install/paper_vla_tb3so101/lib/paper_vla_tb3so101/so101_mision.py) funciones nuevas en el script instalado"
done
for S in 21 22; do
  estado "comparación A5 vs A6, semilla $S: 10 + 10 misiones del experto en paralelo (A5 dominio 85, A6 dominio 87)"
  OVERLAY=/tmp/so101_ws_A5/install bash $V/mision_overlay.sh ik_directa - 10 $S $R/pruebaA5_s$S.csv $V/intentos_mision/pruebaA5 $R/noche14_A5_s$S.log 85 so101_prueba & P1=$!
  OVERLAY=/tmp/so101_ws_A6/install bash $V/mision_overlay.sh ik_directa - 10 $S $R/pruebaA6_s$S.csv $V/intentos_mision/pruebaA6 $R/noche14_A6_s$S.log 87 so101_foto & P2=$!
  wait $P1 $P2
  estado "semilla $S: A5 $(exito $R/pruebaA5_s$S.csv)/10, A6 $(exito $R/pruebaA6_s$S.csv)/10"
done
A5=$(( $(exito $R/pruebaA5_s21.csv) + $(exito $R/pruebaA5_s22.csv) )); A6=$(( $(exito $R/pruebaA6_s21.csv) + $(exito $R/pruebaA6_s22.csv) ))
estado "total: A5 $A5/20, A6 $A6/20 (referencias: A2 3/10, A4 0/20)"
if [ $A6 -gt $A5 ]; then CFG=A6; else CFG=A5; fi
estado "configuración elegida para la tanda final: $CFG -> 20 experto + 20 VLA 40k (semilla 21), con vídeo continuo"
M=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
OVERLAY=/tmp/so101_ws_$CFG/install VIDEO=$V/videos_mision/experto_$CFG bash $V/mision_overlay.sh ik_directa - 20 21 $R/final_misiones_experto_${CFG}_n20_s21.csv $V/intentos_mision/final_experto_$CFG $R/noche14_final_experto.log 85 so101_prueba & P1=$!
OVERLAY=/tmp/so101_ws_$CFG/install VIDEO=$V/videos_mision/vla40k_$CFG bash $V/mision_overlay.sh vla $M 20 21 $R/final_misiones_vla40k_${CFG}_n20_s21.csv $V/intentos_mision/final_vla40k_$CFG $R/noche14_final_vla.log 87 so101_foto & P2=$!
wait $P1 $P2
estado "tanda final ($CFG): experto $(exito $R/final_misiones_experto_${CFG}_n20_s21.csv)/20, VLA 40k $(exito $R/final_misiones_vla40k_${CFG}_n20_s21.csv)/20"
estado "FIN noche 14"
