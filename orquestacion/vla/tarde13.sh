#!/bin/bash
# Tarde 13-nov: prueba A4 (A2 + tolerancia de orientación 0.1 rad) con 20 misiones del experto; elige A2 o A4 por tasa de éxito y lanza la
# tanda final grabada: 20 misiones con el experto y 20 con el VLA de 40k (semilla 21) en paralelo. Estado en vla/registros/ESTADO_TARDE13.txt.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_TARDE13.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
bash $V/monitor_recursos.sh $R/consumo_tarde13.csv & MON=$!
W=/tmp/so101_ws_A4; rm -rf $W; mkdir -p $W/src; cp -r /tmp/so101_ws_A2/src/paper_vla_tb3so101 $W/src/
sed -i -E 's/(yaw_goal_tolerance:\s*)0\.3/\10.1/' $W/src/paper_vla_tb3so101/config/nav2_mision.yaml
(cd $W && source /opt/ros/humble/setup.bash && source $D/colcon/install/setup.bash && colcon build --packages-select paper_vla_tb3so101 > $R/tarde13_build.log 2>&1)
estado "A4 compilado: $(grep -E 'yaw_goal_tolerance|alpha1|recovery_alpha_fast' $W/src/paper_vla_tb3so101/config/nav2_mision.yaml | tr -s ' ' | tr '\n' ' ')"
estado "prueba A4: 20 misiones del experto (semillas 21 y 22 en paralelo)"
OVERLAY=$W/install bash $V/mision_overlay.sh ik_directa - 10 21 $R/pruebaA4_s21.csv $V/intentos_mision/pruebaA4 $R/tarde13_A4_s21.log 87 so101_foto &
OVERLAY=$W/install bash $V/mision_overlay.sh ik_directa - 10 22 $R/pruebaA4_s22.csv $V/intentos_mision/pruebaA4 $R/tarde13_A4_s22.log 85 so101_prueba &
wait
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
A4=$(( $(exito $R/pruebaA4_s21.csv) + $(exito $R/pruebaA4_s22.csv) ))
estado "A4: $A4/20 éxitos (A2 tuvo 3/10)"
if [ $(( A4 * 10 )) -ge $(( 3 * 20 )) ]; then CFG=A4; else CFG=A2; fi
estado "configuración elegida para la tanda final: $CFG -> 20 experto + 20 VLA 40k (semilla 21), con vídeo continuo"
M=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
OVERLAY=/tmp/so101_ws_$CFG/install VIDEO=$V/videos_mision/experto_$CFG bash $V/mision_overlay.sh ik_directa - 20 21 $R/final_misiones_experto_${CFG}_n20_s21.csv $V/intentos_mision/final_experto $R/tarde13_final_experto.log 85 so101_prueba &
OVERLAY=/tmp/so101_ws_$CFG/install VIDEO=$V/videos_mision/vla40k_$CFG bash $V/mision_overlay.sh vla $M 20 21 $R/final_misiones_vla40k_${CFG}_n20_s21.csv $V/intentos_mision/final_vla40k $R/tarde13_final_vla.log 87 so101_foto &
wait
estado "tanda final: experto $(exito $R/final_misiones_experto_${CFG}_n20_s21.csv)/20, VLA 40k $(exito $R/final_misiones_vla40k_${CFG}_n20_s21.csv)/20"
kill $MON; estado "FIN tarde 13"
