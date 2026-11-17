#!/bin/bash
# 15-nov madrugada: sin reentrenar, ¿ejecutar menos acciones por inferencia mejora el agarre del SmolVLA 40k? (informe de diagnóstico, §1.6, paso 2)
# Mismas 50 escenas (semilla 900), pinza 2 N·m, solo VLA (el experto ya está con esas escenas). 2 simulaciones, sin entrenamiento en la GPU.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_MADRUGADA15.txt; cd $D
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5} END {print s+0}'; }
M=$V/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model
estado "INICIO: SmolVLA 40k con 10 y 15 acciones por inferencia (antes 25: 36/50)"
( NACC=10 VLA_PUERTO=5555 bash $V/evaluar_overlay.sh $M 50 vla $R/eval_brazo_A7e2_40k_nacc10_n50_s900.csv $V/intentos_vla_escena/eval_A7e2_40k_nacc10 $R/madrugada15_nacc10.log 87 so101_foto
  estado "40k NACC=10: $(exito $R/eval_brazo_A7e2_40k_nacc10_n50_s900.csv)/50" ) &
sleep 60
( NACC=15 VLA_PUERTO=5556 bash $V/evaluar_overlay.sh $M 50 vla $R/eval_brazo_A7e2_40k_nacc15_n50_s900.csv $V/intentos_vla_escena/eval_A7e2_40k_nacc15 $R/madrugada15_nacc15.log 88 so101_mision
  estado "40k NACC=15: $(exito $R/eval_brazo_A7e2_40k_nacc15_n50_s900.csv)/50" ) &
wait; estado "FIN madrugada15"
