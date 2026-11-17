#!/bin/bash
# 15-nov: copia de evaluar_semilla.sh con el servidor genérico (ACT u otras políticas).
# Antes: copia de evaluar_overlay.sh con la semilla del banco en la variable SEMILLA (900 por defecto); el entorno (SO101_*) pasa a la simulación.
# Evaluación automática del brazo con un modelo SmolVLA: arranca el servidor de la política (GPU), la simulación sin ventana y
# so101_eval_brazo.py (escenas pareadas), graba cada intento VLA y al final cierra todo lo suyo (servidor por PID, simulación por dominio).
# Variable opcional NACC: acciones del bloque que se ejecutan antes de volver a inferir (25 por defecto; menos = más reactivo).
# Uso: bash evaluar.sh <modelo_pretrained_model> <n_escenas> <estrategias> <csv_salida> <carpeta_grabaciones> <registro> [dominio] [particion]
# Reanudable (12-nov): si Gazebo se congela (el registro no avanza en 15 min) se cierra la simulación, se relanza y se sigue desde la
# primera escena incompleta (--desde), hasta 6 veces. Si el CSV ya tiene escenas (p. ej. se amplía de 20 a 50), continúa desde ahí.
MOD=$1; N=$2; EST=$3; OUT=$4; GRAB=$5; LOG=$6; DOM=${7:-85}; PART=${8:-so101_prueba}
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; cd $D; export HF_HOME=$D/hf_cache PYTHONIOENCODING=utf-8
NEST=$(echo $EST | tr ',' '\n' | wc -l)
SRV=""
if echo "$EST" | grep -q vla; then
  env/bin/python vla/servidor_politica_gen.py --modelo $MOD --n-acciones ${NACC:-25} --puerto ${VLA_PUERTO:-5555} > $LOG.servidor 2>&1 & SRV=$!
  for i in $(seq 60); do grep -q escuchando $LOG.servidor && break; sleep 5; done
  grep -q escuchando $LOG.servidor || { echo "servidor no arrancó" >> $LOG; kill $SRV; exit 1; }
fi
# escenas completas en el CSV (todas sus estrategias); se borran las filas de una escena a medias
completas() {
  [ -f $OUT ] || { echo 0; return; }
  /usr/bin/python3 - "$OUT" $NEST <<'P'
import csv, sys, collections
f, nest = sys.argv[1], int(sys.argv[2]); filas = list(csv.DictReader(open(f)))
c = collections.Counter(int(r['escena']) for r in filas); k = 0
while c.get(k, 0) >= nest:
    k += 1
if any(int(r['escena']) >= k for r in filas):
    campos = list(filas[0].keys()); w = csv.DictWriter(open(f, 'w', newline=''), fieldnames=campos); w.writeheader()
    w.writerows(r for r in filas if int(r['escena']) < k)
print(k)
P
}
source $D/ros_env.sh > /dev/null; [ -n "$OVERLAY" ] && source $OVERLAY/setup.bash
export ROS_DOMAIN_ID=$DOM IGN_PARTITION=$PART GZ_PARTITION=$PART
mkdir -p $GRAB; cod=1
for intento in 1 2 3 4 5 6; do
  K=$(completas); [ $K -ge $N ] && { cod=0; break; }
  echo "$(date '+%F %T') intento $intento: escenas $K..$((N - 1))" >> $LOG
  setsid ros2 launch paper_vla_tb3so101 cinematica.launch.py headless:=true > /tmp/so101_eval_${DOM}_launch.log 2>&1 &
  sleep 50
  timeout 30 ros2 param set /so101_manipulator vla_grabar_dir "$GRAB" >> $LOG 2>&1
  timeout 30 ros2 param set /so101_manipulator vla_puerto ${VLA_PUERTO:-5555} >> $LOG 2>&1
  ros2 run paper_vla_tb3so101 so101_eval_brazo.py --n $N --desde $K --seed ${SEMILLA:-900} --estrategias $EST --out $OUT >> $LOG 2>&1 & P=$!
  while kill -0 $P 2>/dev/null; do
    sleep 60
    if [ $(( $(date +%s) - $(stat -c %Y $LOG) )) -gt 900 ]; then
      echo "$(date '+%F %T') sin avance en 15 min (¿Gazebo congelado?): relanzo" >> $LOG
      kill -INT $P 2>/dev/null; sleep 15; kill -KILL $P 2>/dev/null; break
    fi
  done
  wait $P 2>/dev/null; cod=$?
  bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh $DOM > /dev/null 2>&1; sleep 10
done
[ $(completas) -ge $N ] && cod=0
[ -n "$SRV" ] && kill $SRV 2>/dev/null
exit $cod
