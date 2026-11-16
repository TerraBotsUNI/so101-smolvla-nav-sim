#!/bin/bash
# Detiene TODO lo de ROS 2 y Gazebo de UN dominio (para cuando algo se queda congelado).
#   bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh        -> tu dominio (ROS_DOMAIN_ID actual; si no hay, 77)
#   bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh 85     -> el dominio 85
#   bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh --todo -> TODOS los de este usuario (¡también otras simulaciones!)
# Solo toca procesos de este usuario. Primero Ctrl-C (INT), luego TERM y, si siguen colgados, KILL.
DOM="${1:-${ROS_DOMAIN_ID:-77}}"
PATRON='ros2 |/opt/ros/humble/|ign gazebo|ruby /usr/bin/ign|gz sim|rviz2|parameter_bridge|paper_vla_tb3|so101_|lerobot'

buscar() {
  for p in $(pgrep -u "$(id -u)" -f "$PATRON"); do
    [ "$p" = "$$" ] && continue
    if [ "$DOM" = "--todo" ] || tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -qx "ROS_DOMAIN_ID=$DOM"; then echo "$p"; fi
  done
}

P=$(buscar)
if [ -z "$P" ]; then echo "No hay procesos de ROS 2/Gazebo en el dominio $DOM."; exit 0; fi
echo "Dominio $DOM: $(echo $P | wc -w) procesos:"
for p in $P; do echo "  $p $(ps -o args= -p $p 2>/dev/null | cut -c1-90)"; done

for senal in INT TERM KILL; do
  P=$(buscar); [ -z "$P" ] && break
  echo "-> SIG$senal a $(echo $P | wc -w) procesos"
  kill -$senal $P 2>/dev/null
  [ "$senal" = "KILL" ] || sleep 5
done
sleep 1
P=$(buscar)
ROS_DOMAIN_ID=${DOM/--todo/77} ros2 daemon stop >/dev/null 2>&1
# Memoria compartida de Fast DDS que dejan los procesos cerrados a la fuerza: si queda, la siguiente simulación falla
# ("RTPS_TRANSPORT_SHM ... open_and_lock_file failed": no aparece el robot, los spawner mueren, Nav2 no se activa).
# Solo borra segmentos sin dueño vivo: no afecta a otras simulaciones en marcha.
[ -x /opt/ros/humble/bin/fastdds ] && /opt/ros/humble/bin/fastdds shm clean 2>/dev/null | tail -2
if [ -z "$P" ]; then echo "Listo: dominio $DOM limpio."; else echo "Quedan: $P"; fi
