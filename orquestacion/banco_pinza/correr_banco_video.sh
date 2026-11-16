#!/bin/bash
# Banco de sujeción en video (16-nov): pinza 10 N·m (overlay) frente a 2 N·m (instalación actual), con y sin cubos vecinos.
# Cada caso: simulación nueva (cinematica.launch.py, sin Nav2), grabador de cámaras, banco prueba_sujecion_video.py agarrando el AZUL.
# Uso: bash correr_banco_video.sh caso1 [caso2 ...]   con caso = <par>_<vecinos>_<n>, p. ej. 10Nm_con_1, 2Nm_sin_1
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; B=$D/vla/banco_video; OV=$D/overlays/pinza_10Nm/install
L=$D/colcon/install/paper_vla_tb3so101/lib/paper_vla_tb3so101
DOM=87; PART=so101_foto
log() { echo "$(date '+%F %T') $*" | tee -a $B/registro.log; }

parar() {   # solo lo que lanzó este script (grupos de procesos propios) y, por si acaso, lo que quede en el dominio 87
  [ -n "$G" ] && kill -INT $G 2>/dev/null && sleep 6
  [ -n "$LP" ] && { kill -INT -$LP 2>/dev/null; sleep 10; kill -TERM -$LP 2>/dev/null; sleep 5; kill -KILL -$LP 2>/dev/null; }
  bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh $DOM >> $B/registro.log 2>&1
  G=""; LP=""; sleep 5
}
trap 'parar; exit 1' INT TERM

for caso in "$@"; do
  PAR=${caso%%_*}; VEC=$(echo $caso | cut -d_ -f2)
  for intento in 1 2 3; do
    C=$B/$caso; [ $intento -gt 1 ] && C=$B/${caso}_reintento$intento
    rm -rf $C; mkdir -p $C
    log "=== $caso (intento $intento): pinza $PAR, vecinos $VEC -> $C"
    (
      source $D/ros_env.sh > /dev/null
      [ "$PAR" = 10Nm ] && source $OV/setup.bash
      export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART GZ_PARTITION=$PART PYTHONIOENCODING=utf-8
      echo "prefijo: $(ros2 pkg prefix paper_vla_tb3so101)" > $C/config.txt
      exec setsid ros2 launch paper_vla_tb3so101 cinematica.launch.py headless:=true > $C/launch.log 2>&1
    ) &
    LP=$!   # setsid con exec: el PID es también el PGID del lanzamiento (si setsid hace fork, se busca abajo)
    sleep 3; PG=$(ps -o pgid= -p $LP 2>/dev/null | tr -d ' '); [ -n "$PG" ] && LP=$PG
    echo "pgid lanzamiento: $LP" >> $C/config.txt
    sleep 75
    (   # entorno en subcapa: así el overlay de 10 N·m no se arrastra al caso siguiente
      source $D/ros_env.sh > /dev/null; [ "$PAR" = 10Nm ] && source $OV/setup.bash
      export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART GZ_PARTITION=$PART PYTHONIOENCODING=utf-8
      timeout 20 ros2 topic echo --once --full-length /tb3_so101/robot_description 2>/dev/null | python3 $B/limite_pinza.py >> $C/config.txt 2>&1
      setsid /usr/bin/python3 $L/so101_grabador.py --dir $C/video --fps 5 --size 480 > $C/grabador.log 2>&1 &
      echo $! > $C/grabador.pid
      for i in $(seq 30); do [ -f $C/video/listo ] && break; sleep 2; done
      [ -f $C/video/listo ] || log "AVISO: el grabador no está listo"
      ARG=""; [ "$VEC" = sin ] && ARG="--sin-vecinos"
      PYTHONPATH=$L:$PYTHONPATH timeout 400 /usr/bin/python3 $B/prueba_sujecion_video.py $C/resultado.csv cerrar azul $ARG --traza $C/traza.csv > $C/banco.out 2>&1
    )
    G=$(cat $C/grabador.pid 2>/dev/null)
    log "banco terminó : $(tr '\n' ' ' < $C/banco.out | cut -c1-400)"
    parar
    if grep -q "pinza .* rad; QUIETO" $C/banco.out && [ $(wc -l < $C/resultado.csv) -ge 4 ]; then log "$caso OK"; break; fi
    log "$caso: agarre fallido o incompleto; reintento"
  done
done
log "fin de la tanda: $*"
