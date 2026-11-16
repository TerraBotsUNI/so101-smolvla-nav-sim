#!/bin/bash
# Colector de demostraciones en un dominio/partición propios (para correr varios en paralelo sin mezclarse).
# Uso: bash colector.sh <dominio> <particion> <carpeta_salida> <episodios> <semilla> <registro>
# Lanza Gazebo sin ventana + servidor del brazo, graba con so101_demos.py y al terminar cierra TODO lo de su dominio (parar_sim.sh).
# Doble vigilancia contra Gazebo congelado (12-nov): so101_demos.py sale con código 3 si un episodio pasa de 300 s de tiempo real,
# y además aquí, si el registro no avanza en 15 min, se corta la corrida. El orquestador vuelve a llamar a este script con lo que falte.
DOM=$1; PART=$2; OUT=$3; N=$4; SEED=$5; LOG=$6
source ${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}/ros_env.sh > /dev/null
export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART GZ_PARTITION=$PART
setsid ros2 launch paper_vla_tb3so101 cinematica.launch.py headless:=true > /tmp/so101_colector_${DOM}_launch.log 2>&1 &
sleep 50
touch $LOG
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
