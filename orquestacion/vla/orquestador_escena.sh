#!/bin/bash
# Orquestador «cámara de escena» (12-nov-2026): segunda ronda de datos tras montar la cámara del mástil.
#   1) Colectores A (dominio 85) y B (dominio 86) en paralelo: 220 episodios cada uno en demos/crudas_escena_a y _b
#      (muñeca + escena + frontal). Se relanzan solos si Gazebo se congela (hasta 20 tandas).
#   2) Ajuste temprano de SmolVLA (8000 pasos) en cuanto haya 150 episodios exitosos (la GPU está libre mientras se graba).
#   3) Ajuste definitivo (20000 pasos) con todo lo grabado al terminar los colectores.
#   4) Evaluación automática en 20 escenas pareadas: definitivo (vla + experto ik_directa) y temprano (vla), con grabación de cada intento.
#   Monitor de consumo cada 30 s en vla/registros/consumo_escena.csv. Estado en vla/registros/ESTADO_ESCENA.txt.
# Parar: bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh 85 ; ... 86 ; y matar este script / lerobot-train / servidor_politica por PID.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_ESCENA.txt; mkdir -p $R
A=$D/demos/crudas_escena_a; B=$D/demos/crudas_escena_b; mkdir -p $A $B
estado() { echo "$(date '+%F %T') $*" >> $E; }
exitosos() { cat $A/ep_*/meta.json $B/ep_*/meta.json 2>/dev/null | grep -c '"exito": true'; }
cuantos() { ls -d $1/ep_* 2>/dev/null | wc -l; }
estado "ORQUESTADOR ESCENA: 2 colectores + ajuste temprano y definitivo + evaluación automática + monitor de consumo"
bash $V/monitor_recursos.sh $R/consumo_escena.csv & MON=$!

colector_resiliente() {   # dominio particion carpeta objetivo semilla_base registro
  local DOM=$1 PART=$2 OUT=$3 OBJ=$4 SB=$5 LOG=$6
  for k in $(seq 20); do
    local falta=$((OBJ - $(cuantos $OUT))); [ $falta -le 0 ] && break
    estado "colector $DOM: tanda $k, faltan $falta episodios"
    bash $V/colector.sh $DOM $PART $OUT $falta $((SB + 10 * k)) $LOG; sleep 10
  done
  estado "colector $DOM terminado: $(cuantos $OUT) episodios en $OUT"
}
colector_resiliente 85 so101_prueba $A 300 1100 $R/escena_demos_a.log & CA=$!
sleep 90   # escalonado: que no arranquen las dos simulaciones a la vez
colector_resiliente 86 so101_b $B 300 2200 $R/escena_demos_b.log & CB=$!

convertir() {  # salida repo registro
  rm -rf $D/$1
  cd $D && HF_HOME=$D/hf_cache env/bin/python $V/convertir_demos_lerobot.py --crudas demos/crudas_escena_a demos/crudas_escena_b --salida $1 --repo-id $2 > $3 2>&1
  grep -q "^listo" $3
}

# --- ajuste temprano
TEMP=""
while [ $(exitosos) -lt 150 ] && { kill -0 $CA 2>/dev/null || kill -0 $CB 2>/dev/null; }; do sleep 120; done
if [ $(exitosos) -ge 60 ]; then
  estado "TEMPRANO: $(exitosos) episodios exitosos -> conversión y ajuste de 8000 pasos"
  if convertir demos/lerobot_escena_temprano local/so101_escena_temprano $R/escena_conversion_temprano.log; then
    TEMP=$V/entrenos/smolvla_escena_temprano_$(date +%H%M)
    CAM2=scene bash $V/entrenar.sh $D/demos/lerobot_escena_temprano local/so101_escena_temprano $TEMP 8000 32 $R/escena_entreno_temprano.log
    estado "TEMPRANO terminado (código $?) en $TEMP"
  else estado "TEMPRANO: falló la conversión"; fi
fi

# --- ajuste definitivo
wait $CA $CB
estado "COLECTORES terminados: $(exitosos) exitosos ($(cuantos $A) + $(cuantos $B) grabados)"
DEF=""
if convertir demos/lerobot_escena local/so101_escena $R/escena_conversion.log; then
  DEF=$V/entrenos/smolvla_escena_definitivo_$(date +%H%M)
  estado "DEFINITIVO: $(grep '^listo' $R/escena_conversion.log) -> ajuste de 20000 pasos"
  CAM2=scene bash $V/entrenar.sh $D/demos/lerobot_escena local/so101_escena $DEF 20000 32 $R/escena_entreno_definitivo.log
  estado "DEFINITIVO terminado (código $?) en $DEF"
else estado "DEFINITIVO: falló la conversión (ver escena_conversion.log)"; fi

# --- evaluación automática (20 escenas pareadas, semilla 900)
ultimo() { ls -d $1/checkpoints/[0-9]*/pretrained_model 2>/dev/null | sort | tail -1; }
F=$(date +%F)
if [ -n "$DEF" ] && [ -n "$(ultimo $DEF)" ]; then
  estado "EVAL definitivo: $(ultimo $DEF) | vla + ik_directa, 20 escenas"
  bash $V/evaluar.sh $(ultimo $DEF) 20 vla,ik_directa $R/eval_escena_definitivo_n20_$F.csv $V/intentos_vla_escena/definitivo $R/escena_eval_definitivo.log
  estado "EVAL definitivo terminado (código $?)"
fi
if [ -n "$TEMP" ] && [ -n "$(ultimo $TEMP)" ]; then
  estado "EVAL temprano: $(ultimo $TEMP) | vla, 20 escenas"
  bash $V/evaluar.sh $(ultimo $TEMP) 20 vla $R/eval_escena_temprano_n20_$F.csv $V/intentos_vla_escena/temprano $R/escena_eval_temprano.log
  estado "EVAL temprano terminado (código $?)"
fi
kill $MON 2>/dev/null
estado "FIN orquestador escena"
