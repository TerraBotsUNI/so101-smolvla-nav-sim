#!/bin/bash
# Uso (en CADA terminal):  source $PROYECTO/ros_env.sh   (los orquestadores esperan una copia en $PROYECTO/ros_env.sh)
# Versión usada en la estación de trabajo; solo se sustituyó la ruta del proyecto por la variable PROYECTO.
PROYECTO=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}
# Aísla esta simulación de otras sesiones de la workstation (otro dominio ROS y otra partición de Gazebo).
# ROS 2 Humble necesita el Python 3.10 del sistema: si hay (base) de conda activo en esta terminal, se quita de PATH
# (si no, `python3` es el 3.13 de conda y falla "No module named rclpy._rclpy_pybind11"). Los envs de LeRobot se usan con su ruta completa.
if [ -n "$CONDA_PREFIX" ] || echo "$PATH" | grep -q '/miniconda3/'; then
  export PATH=$(echo "$PATH" | tr ':' '
' | grep -v '/miniconda3/' | paste -sd:)
  unset CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL CONDA_PROMPT_MODIFIER CONDA_EXE CONDA_PYTHON_EXE PYTHONHOME
  hash -r
fi
source /opt/ros/humble/setup.bash
source $PROYECTO/colcon/install/setup.bash
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-77}   # dominio usado en la WS; cámbielo si otra sesión ROS usa el mismo
export IGN_PARTITION=${IGN_PARTITION:-paper_vla}
export GZ_PARTITION=$IGN_PARTITION
echo "Entorno del paper listo (ROS_DOMAIN_ID=$ROS_DOMAIN_ID, partición $IGN_PARTITION)."
