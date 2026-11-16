#!/bin/bash
# Igual que mision.sh pero con una configuración de Nav2/AMCL de prueba superpuesta (OVERLAY=<install de un espacio de trabajo aparte>)
# y grabación continua de las 3 cámaras de toda la tanda (VIDEO=<carpeta>). Reanudable.
# Uso: OVERLAY=/tmp/so101_ws_A4/install VIDEO=<dir> bash mision_overlay.sh <ik_directa|vla> <modelo|-> <n> <semilla> <csv> <grabaciones> <registro> <dominio> <particion>
EST=$1; MOD=$2; N=$3; SEED=$4; OUT=$5; GRAB=$6; LOG=$7; DOM=$8; PART=$9
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; cd $D; export HF_HOME=$D/hf_cache PYTHONIOENCODING=utf-8
SRV=""
if [ "$EST" = vla ]; then
  env/bin/python vla/servidor_politica.py --modelo $MOD --puerto 5555 > $LOG.servidor 2>&1 & SRV=$!
  for i in $(seq 60); do grep -q escuchando $LOG.servidor && break; sleep 5; done
  grep -q escuchando $LOG.servidor || { echo "servidor no arrancó" >> $LOG; kill $SRV; exit 1; }
fi
hechas() { [ -f $OUT ] && echo $(( $(wc -l < $OUT) - 1 )) || echo 0; }
source $D/ros_env.sh > /dev/null; [ -n "$OVERLAY" ] && source $OVERLAY/setup.bash
export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART GZ_PARTITION=$PART
L=$D/colcon/install/paper_vla_tb3so101/lib/paper_vla_tb3so101
mkdir -p $GRAB; touch $LOG; echo "config Nav2/AMCL: $(ros2 pkg prefix paper_vla_tb3so101)" >> $LOG
for intento in 1 2 3 4 5 6; do
  K=$(hechas); [ $K -ge $N ] && break
  echo "$(date '+%F %T') intento $intento: misiones $K..$((N - 1)) ($EST)" >> $LOG
  setsid ros2 launch paper_vla_tb3so101 cinematica.launch.py headless:=true nav:=true controller:=mision strategy:=$EST > /tmp/so101_mision_${DOM}_launch.log 2>&1 &
  sleep 75
  timeout 30 ros2 param set /so101_manipulator vla_grabar_dir "$GRAB" >> $LOG 2>&1
  G=""; [ -n "$VIDEO" ] && { mkdir -p $VIDEO; /usr/bin/python3 $L/so101_grabador.py --dir $VIDEO/tramo_$intento --fps 5 > $VIDEO/grabador_$intento.log 2>&1 & G=$!; }
  ros2 run paper_vla_tb3so101 so101_mision.py --n $N --desde $K --seed $SEED --out $OUT >> $LOG 2>&1 & P=$!
  while kill -0 $P 2>/dev/null; do
    sleep 60
    if [ $(( $(date +%s) - $(stat -c %Y $LOG) )) -gt 1200 ]; then
      echo "$(date '+%F %T') sin avance en 20 min: relanzo" >> $LOG; kill -INT $P 2>/dev/null; sleep 15; kill -KILL $P 2>/dev/null; break
    fi
  done
  wait $P 2>/dev/null; [ -n "$G" ] && { kill -INT $G; sleep 5; }
  bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh $DOM > /dev/null 2>&1; sleep 10
done
[ -n "$SRV" ] && kill $SRV 2>/dev/null
[ $(hechas) -ge $N ]
