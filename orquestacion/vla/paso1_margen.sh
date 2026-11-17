#!/bin/bash
# 15-nov, paso 1 del plan (diagnóstico de fallos): tolerancia del agarre del EXPERTO. Barrido de MARGEN (18, 22, 26, 30 mm) sin ruido y con
# ruido inyectado (±3 mm en x e y, ±10° en el giro estimado), en el banco con disposición de MISIÓN (pedido en cualquier posición de la fila),
# semilla 910 (nueva), 30 escenas, solo el experto. 2 simulaciones, sin GPU. Espera a que termine madrugada15.sh y recompila el paquete principal.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_PASO1.txt; cd $D
estado() { echo "$(date '+%F %T') $*" >> $E; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, '{s+=$5;n++} END {print s+0 "/" n+0}'; }
until grep -q "FIN madrugada15" $R/ESTADO_MADRUGADA15.txt 2>/dev/null; do sleep 60; done
estado "INICIO paso 1 (madrugada15 terminada): recompilo el paquete principal con SO101_MARGEN/SO101_RUIDO_* y --disposicion mision"
(cd $D/colcon && source /opt/ros/humble/setup.bash && colcon build --base-paths ~/ros2_ws/src/paper_rover_vla_2025 --packages-select paper_vla_tb3so101) >> $R/paso1_compilar.log 2>&1; estado "compilación (código $?)"
grep -q SO101_MARGEN $D/colcon/install/paper_vla_tb3so101/lib/paper_vla_tb3so101/so101_trial.py || { estado "ERROR: el instalado no tiene SO101_MARGEN"; exit 1; }
corre() {   # margen_mm ruido_mm ruido_deg dominio particion
  local tag="m$1_r$2"
  SO101_DISPOSICION=mision SO101_MARGEN=0.0$1 SO101_RUIDO_MM=$2 SO101_RUIDO_DEG=$3 SO101_RUIDO_SEED=7 \
    SEMILLA=910 bash $V/evaluar_semilla.sh - 30 ik_directa $R/paso1_experto_${tag}_mision_s910.csv $V/intentos_vla_escena/paso1_$tag $R/paso1_$tag.log $4 $5
  estado "experto MARGEN $1 mm, ruido ±$2 mm/±$3°: $(exito $R/paso1_experto_${tag}_mision_s910.csv)"
}
( for m in 18 22 26 30; do corre $m 0 0 87 so101_foto; done ) &
sleep 60
( for m in 18 22 26 30; do corre $m 3 10 88 so101_mision; done ) &
wait; estado "FIN paso 1"
