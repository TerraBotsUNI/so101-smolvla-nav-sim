#!/bin/bash
# Noche 14-nov (c): al terminar noche14b, banco de la pinza con el límite de esfuerzo del servo real (problema 31).
# A7e2 / A7e1 = A5 con <limit effort> de la articulación gripper en 2.0 / 1.0 N·m (antes 10). Para cada una: banco prueba_sujecion.py con
# el cubo lateral (azul) y el central (verde): ¿deriva el robot solo? ¿sigue agarrando? Resultados en vla/registros/ESTADO_NOCHE14.txt.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE14.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
while pgrep -f "bash vla/noche14b.sh" > /dev/null; do sleep 60; done
estado "(c) banco de la pinza con esfuerzo limitado (A7e2, A7e1)"
L=$D/colcon/install/paper_vla_tb3so101/lib/paper_vla_tb3so101
for C in A7e2 A7e1 A7e2 A7e1; do
  W=/tmp/so101_ws_$C; OUT=$R/banco_pinza_${C}_2026-11-14.csv
  ( source $D/ros_env.sh > /dev/null; source $W/install/setup.bash; export ROS_DOMAIN_ID=87 IGN_PARTITION=so101_foto GZ_PARTITION=so101_foto
    setsid ros2 launch paper_vla_tb3so101 cinematica.launch.py headless:=true > /tmp/banco_${C}_launch.log 2>&1 &
    sleep 75
    cd $L && PYTHONPATH=$L:$PYTHONPATH timeout 1200 /usr/bin/python3 ~/ros2_ws/src/paper_rover_vla_2025/tools/prueba_sujecion.py $OUT.tmp cerrar azul,verde,azul > $R/banco_pinza_${C}.out 2>&1
    cat $OUT.tmp >> $OUT; rm -f $OUT.tmp
    bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh 87 > /dev/null 2>&1; sleep 10 )
  estado "$C: $(grep -E 'QUIETO|agarre fallido' $R/banco_pinza_${C}.out | sed -E 's/.*apriete //; s/: pinza.*QUIETO 8 s:/:/; s/; cubo z.*//' | tr '\n' '|')"
  estado "$C giros (dif odometría-real): $(grep -E 'giro_avance' $R/banco_pinza_${C}.out | sed -E 's/.*diferencia *//; s/ *cubo z.*//' | tr '\n' ' ')"
done
estado "FIN banco pinza"
