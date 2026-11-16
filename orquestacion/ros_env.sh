#!/bin/bash
# Entorno ROS 2 para cada terminal (RECONSTRUIDO a partir de la documentación; verificar contra el ros_env.sh original de la WS).
# Uso: source orquestacion/ros_env.sh   (los orquestadores esperan una copia en $PROYECTO/ros_env.sh)
# - Quita conda del PATH: si no, python3 es el de conda y rclpy falla.
# - Carga ROS 2 Humble y el workspace compilado en $PROYECTO/colcon/install.
# - Aísla la simulación: cada simulación en paralelo necesita ROS_DOMAIN_ID e IGN/GZ_PARTITION distintos.
PROYECTO=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}
PATH=$(echo "$PATH" | tr ':' '\n' | grep -v -i conda | paste -sd ':' -)
export PATH
unset CONDA_PREFIX CONDA_DEFAULT_ENV PYTHONPATH
source /opt/ros/humble/setup.bash
[ -f "$PROYECTO/colcon/install/setup.bash" ] && source "$PROYECTO/colcon/install/setup.bash"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-77}
export IGN_PARTITION=${IGN_PARTITION:-paper_vla}
export GZ_PARTITION=$IGN_PARTITION
echo "ROS 2 Humble listo: ROS_DOMAIN_ID=$ROS_DOMAIN_ID IGN_PARTITION=$IGN_PARTITION"
