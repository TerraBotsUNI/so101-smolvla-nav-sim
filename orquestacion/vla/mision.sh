#!/bin/bash
# Tanda de misiones completas (Nav2 -> recoger -> Nav2 -> colocar) con el experto o con el VLA haciendo el brazo.
# Uso: bash mision.sh <ik_directa|vla> <modelo_o_-> <n> <semilla> <csv_salida> <carpeta_grabaciones> <registro> [dominio] [particion]
# Con «vla» arranca el servidor de la política y lanza la simulación con strategy:=vla. Reanudable: si el registro no avanza en 20 min
# se relanza la simulación y se sigue desde la siguiente misión (--desde, misma secuencia de colores), hasta 6 veces.
EST=$1; MOD=$2; N=$3; SEED=$4; OUT=$5; GRAB=$6; LOG=$7; DOM=${8:-88}; PART=${9:-so101_mision}
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; cd $D; export HF_HOME=$D/hf_cache PYTHONIOENCODING=utf-8
SRV=""
if [ "$EST" = vla ]; then
  env/bin/python vla/servidor_politica.py --modelo $MOD > $LOG.servidor 2>&1 & SRV=$!
  for i in $(seq 60); do grep -q escuchando $LOG.servidor && break; sleep 5; done
  grep -q escuchando $LOG.servidor || { echo "servidor no arrancó" >> $LOG; kill $SRV; exit 1; }
fi
hechas() { [ -f $OUT ] && echo $(( $(wc -l < $OUT) - 1 )) || echo 0; }
source $D/ros_env.sh > /dev/null
export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART GZ_PARTITION=$PART
mkdir -p $GRAB; touch $LOG
for intento in 1 2 3 4 5 6; do
  K=$(hechas); [ $K -ge $N ] && break
  echo "$(date '+%F %T') intento $intento: misiones $K..$((N - 1)) ($EST)" >> $LOG
  setsid ros2 launch paper_vla_tb3so101 cinematica.launch.py headless:=true nav:=true controller:=mision strategy:=$EST > /tmp/so101_mision_${DOM}_launch.log 2>&1 &
  sleep 75
  timeout 30 ros2 param set /so101_manipulator vla_grabar_dir "$GRAB" >> $LOG 2>&1
  ros2 run paper_vla_tb3so101 so101_mision.py --n $N --desde $K --seed $SEED --out $OUT >> $LOG 2>&1 & P=$!
  while kill -0 $P 2>/dev/null; do
    sleep 60
    if [ $(( $(date +%s) - $(stat -c %Y $LOG) )) -gt 1200 ]; then
      echo "$(date '+%F %T') sin avance en 20 min (¿Gazebo congelado?): relanzo" >> $LOG
      kill -INT $P 2>/dev/null; sleep 15; kill -KILL $P 2>/dev/null; break
    fi
  done
  wait $P 2>/dev/null
  bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh $DOM > /dev/null 2>&1; sleep 10
done
[ -n "$SRV" ] && kill $SRV 2>/dev/null
[ $(hechas) -ge $N ]
