#!/bin/bash
# 15-nov: comparación MPPI/DWB/RPP con el robot del SO-101 (LiDAR funcionando). Cada ensayo con simulación nueva, ruta inicio → recojo
# (2.0, 1.5, 0) de config/ubicaciones.yaml, brazo plegado. Configuración: vla/nav_so101/nav2_so101_<ctrl>.yaml (= misión salvo el controlador).
# Uso: nav_batch_so101.sh <ctrl> <n> <dominio> [inicio]   → vla/registros/nav_so101_<ctrl>.csv y trazas en vla/registros/trazas_nav_so101/
CTRL=${1:-mppi}; N=${2:-30}; DOM=${3:-87}; START=${4:-1}
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; mkdir -p $R/trazas_nav_so101
source $D/ros_env.sh > /dev/null
export ROS_DOMAIN_ID=$DOM IGN_PARTITION=nav_so101_$DOM GZ_PARTITION=nav_so101_$DOM
PF=$V/nav_so101/nav2_so101_$CTRL.yaml; W=$(ros2 pkg prefix paper_vla_tb3so101)/share/paper_vla_tb3so101/worlds/paper_vla_arena.sdf
OUT=$R/nav_so101_$CTRL.csv; STAT=$R/nav_so101_$CTRL.txt
for RUN in $(seq $START $((START+N-1))); do
  LOG=/tmp/nav_so101_${CTRL}_${DOM}.log
  setsid ros2 launch paper_vla_tb3so101 nav.launch.py controller:=$CTRL params_file:=$PF world:=$W headless:=true < /dev/null > $LOG 2>&1 &
  LP=$!; sleep 1; PG=$(ps -o pgid= -p $LP | tr -d ' '); ALL=0
  for i in $(seq 1 36); do sleep 5; ok=0
    for n in map_server amcl controller_server planner_server behavior_server bt_navigator; do
      s=$(timeout 6 ros2 lifecycle get /$n 2>/dev/null | head -1); [ "$s" = "active [3]" ] && ok=$((ok+1)); done
    [ $ok -eq 6 ] && { ALL=1; break; }; done
  echo "$(date '+%F %T') ensayo $RUN nav2_activo=$ALL carga=$(cut -d' ' -f1 /proc/loadavg)" >> $STAT
  if [ $ALL -eq 1 ]; then sleep 3
    timeout 220 ros2 run paper_vla_tb3so101 nav_trial.py --controller $CTRL --run-id $RUN --timeout 150 --goal 2.0 1.5 0.0 --out $OUT --trace $R/trazas_nav_so101/traza_${CTRL}_$RUN.json 2>&1 | tail -1 | cut -c1-300 >> $STAT
    echo "  avisos MPPI/controlador 'missed rate': $(grep -c 'missed its desired rate' $LOG)" >> $STAT
  fi
  kill -INT -- -$PG 2>/dev/null; sleep 6; kill -TERM -- -$PG 2>/dev/null; sleep 2; kill -KILL -- -$PG 2>/dev/null; sleep 3
  bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh $DOM > /dev/null 2>&1
done
echo "$(date '+%F %T') FIN $CTRL" >> $STAT
