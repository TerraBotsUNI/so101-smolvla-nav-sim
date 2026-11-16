#!/bin/bash
# Ablación de cobertura (16-nov): copia de vla/colector.sh que graba con la pinza a 10 N·m (overlay overlays/pinza_10Nm, que solo cambia el
# effort de la pinza en el URDF; el resto del paquete es idéntico a colcon/install) y COMPRUEBA en la simulación ya lanzada que la pinza
# tiene effort="10" antes de grabar. Si no lo tiene, no graba nada y sale con código 5.
# Uso: bash colector_10Nm.sh <dominio> <particion> <carpeta_salida> <episodios> <semilla> <registro>
# El entorno SO101_DISPOSICION / SO101_MARGEN pasa a so101_demos.py (lo fija el orquestador).
DOM=$1; PART=$2; OUT=$3; N=$4; SEED=$5; LOG=$6
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; OV=$D/overlays/pinza_10Nm/install
source $D/ros_env.sh > /dev/null
source $OV/setup.bash
export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART GZ_PARTITION=$PART PYTHONIOENCODING=utf-8
touch $LOG
echo "$(date '+%F %T') colector $DOM: prefijo $(ros2 pkg prefix paper_vla_tb3so101) | SO101_DISPOSICION=$SO101_DISPOSICION SO101_MARGEN=$SO101_MARGEN" >> $LOG
setsid ros2 launch paper_vla_tb3so101 cinematica.launch.py headless:=true > /tmp/so101_colector_${DOM}_launch.log 2>&1 &
sleep 50
LIM=$(timeout 30 ros2 topic echo --once --full-length /tb3_so101/robot_description 2>/dev/null | python3 $D/vla/banco_video/limite_pinza.py)
echo "$(date '+%F %T') colector $DOM: $LIM" >> $LOG
if ! echo "$LIM" | grep -q 'effort="10"'; then
  echo "$(date '+%F %T') colector $DOM: la pinza NO está a 10 N·m -> no grabo" >> $LOG
  bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh $DOM > /dev/null 2>&1; exit 5
fi
timeout 25200 ros2 run paper_vla_tb3so101 so101_demos.py --n $N --seed $SEED --out $OUT >> $LOG 2>&1 & P=$!
while kill -0 $P 2>/dev/null; do
  sleep 60
  if [ $(( $(date +%s) - $(stat -c %Y $LOG) )) -gt 900 ]; then
    echo "$(date '+%F %T') colector $DOM: registro sin avanzar 15 min -> corto la corrida" >> $LOG
    kill -INT $P 2>/dev/null; sleep 15; kill -KILL $P 2>/dev/null; break
  fi
done
wait $P 2>/dev/null; echo "$(date '+%F %T') colector $DOM: so101_demos terminó con código $?" >> $LOG
bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh $DOM > /dev/null 2>&1
