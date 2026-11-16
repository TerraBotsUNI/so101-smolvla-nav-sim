# Carpeta del VLA (segunda iteración del paper)

Aquí vive todo lo que NO es ROS: entorno Python 3.12 con LeRobot 0.6.1 (`env/`), código de LeRobot (`lerobot_src/`), modelos (`hf_cache/`), demostraciones (`demos/`), conversión y entrenamientos (`vla/`) y la evaluación en LIBERO de la v1 (`libero_*`).
Lo de ROS está en `~/ros2_ws/src/paper_rover_vla_2025/` (paquetes, launch, scripts del robot y de la misión).

Documentación completa: `~/ros2_ws/src/paper_rover_vla_2025/docs/DOCUMENTACION_TRANSFERENCIA_V2.md` (qué hace cada archivo, comandos, problemas y soluciones) y `docs/GUIA_V2_SO101.md` (recetas).

| Archivo | Uso |
|---|---|
| `vla/convertir_demos_lerobot.py` | `env/bin/python vla/convertir_demos_lerobot.py --crudas demos/crudas --salida demos/lerobot_so101_cubos` |
| `vla/noche.sh` | cadena demostraciones -> conversión -> ajuste de SmolVLA; estado en `vla/registros/ESTADO_NOCHE.txt` |
| `vla/entrenos/` | checkpoints de SmolVLA ajustado |
| `ros_env.sh` | entorno de ROS para cada terminal (dominio 77) |
