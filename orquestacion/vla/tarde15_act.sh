#!/bin/bash
# 15-nov tarde: evaluación de ACT (tercera política, mismas 457 demostraciones que SmolVLA 40k) en los dos bancos, 2 simulaciones.
# Espera a que terminen paso2_4.sh (evaluación del VLA v2) y manana15_experto26.sh, para no pasar de 2 simulaciones ni compartir la GPU.
# 25 acciones por inferencia, igual que SmolVLA. Servidor genérico: vla/servidor_politica_gen.py (vla/evaluar_gen.sh).
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_ACT.txt; cd $D
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5;n++} END {print s+0 "/" n+0}'; }
until grep -q "FIN pasos 2-4" $R/ESTADO_PASO2.txt 2>/dev/null && grep -q "FIN experto m26" $R/ESTADO_MANANA15.txt 2>/dev/null; do sleep 120; done
MA=$V/entrenos/act_escena_40k/checkpoints/040000/pretrained_model
estado "INICIO evaluación ACT (40k pasos) en los bancos s900 (disposición de demostración) y s910 (disposición de misión)"
( SO101_DISPOSICION=demo SEMILLA=900 NACC=25 VLA_PUERTO=5555 bash $V/evaluar_gen.sh $MA 50 vla $R/eval_brazo_act_demo_s900.csv $V/intentos_vla_escena/eval_act_demo_s900 $R/tarde15_act_s900.log 87 so101_foto
  estado "ACT banco demo s900: $(exito $R/eval_brazo_act_demo_s900.csv) [SmolVLA 40k 36/50, experto 18 mm 44/50]" ) &
sleep 60
( SO101_DISPOSICION=mision SEMILLA=910 NACC=25 VLA_PUERTO=5556 bash $V/evaluar_gen.sh $MA 50 vla $R/eval_brazo_act_mision_s910.csv $V/intentos_vla_escena/eval_act_mision_s910 $R/tarde15_act_s910.log 88 so101_mision
  estado "ACT banco misión s910: $(exito $R/eval_brazo_act_mision_s910.csv)" ) &
wait; estado "FIN evaluación ACT"
