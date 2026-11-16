#!/bin/bash
# 14-nov: al terminar noche14g, recompila el paquete principal (ya con A7e2) en colcon/ (nunca en ~/ros2_ws) y comprueba los 3 cambios instalados.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; R=$D/vla/registros; E=$R/ESTADO_NOCHE14.txt
while pgrep -f "bash vla/noche14g.sh" > /dev/null; do sleep 60; done
cd $D/colcon && source /opt/ros/humble/setup.bash && colcon build --base-paths ~/ros2_ws/src/paper_rover_vla_2025 --packages-select paper_vla_tb3so101 > $R/compilar_principal_A7e2.log 2>&1
I=$D/colcon/install/paper_vla_tb3so101
echo "$(date '+%F %T') paquete principal recompilado con A7e2: afinar=$(grep -c 'def afinar' $I/lib/paper_vla_tb3so101/so101_mision.py) pinza=$(grep -A3 'moving_jaw_so101_v1_link" />' $I/share/paper_vla_tb3so101/urdf/so101.urdf.xacro | grep -o 'effort="[0-9.]*"') amcl_alpha1=$(grep -m1 'alpha1:' $I/share/paper_vla_tb3so101/config/nav2_mision.yaml | tr -s ' ')" >> $E
