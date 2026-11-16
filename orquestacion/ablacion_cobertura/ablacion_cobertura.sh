#!/bin/bash
# ABLACIÓN DE COBERTURA (preparada el 16-nov-2026; NO lanzar sin el OK del autor).
# Pregunta: ¿el 0/18 del extremo derecho de SmolVLA 40k se debe solo a la cobertura de los datos (el pedido siempre al centro) o también al
# cambio de receta de la v2 (margen 26 mm y pinza 2 N·m al grabar)? Se reentrena SmolVLA con la receta ORIGINAL de la primera ronda
# (margen 18 mm, pinza 10 N·m al grabar, ~457 demostraciones exitosas, 40 000 pasos, lote 32, cámaras muñeca + escena) cambiando SOLO
# la disposición: SO101_DISPOSICION=mision (pedido a la izquierda, al centro o a la derecha).
#
# Etapas (cada una deja una línea «HECHO <etapa>» en ESTADO_ABLACION.txt; al relanzar se saltan las hechas):
#   1) demos      : 2 colectores en paralelo (dominios 87 y 88), pinza 10 N·m por overlay, hasta 229 + 228 = 457 éxitos. Sin entrenamiento.
#   2) conversion : selección de exactamente 457 episodios exitosos (enlaces) y conversión a LeRobot (acción = estado siguiente, como el 40k).
#   3) entreno    : SmolVLA 40 000 pasos, lote 32, CAM2=scene (entrenar.sh, igual que noche3_entreno40k.sh). Sin simulaciones.
#   4) evaluacion : pinza 2 N·m (instalación actual, sin overlay); s910 disposición misión (dominio 87, puerto 5555) y s900 disposición
#                   demo (dominio 88, puerto 5556) en paralelo, un servidor de política por simulación, 50 escenas cada uno.
#   5) resumen    : éxito por posición (izq./centro/der.) frente a 40k y v2 en las mismas escenas.
#
# Lanzamiento (desde cualquier carpeta; no depende de la terminal):
#   nohup setsid bash ${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}/vla/ablacion_cobertura/ablacion_cobertura.sh \
#     > ${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}/vla/registros/ablacion_cobertura.out 2>&1 < /dev/null &
# Seguimiento: cat ${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}/vla/registros/ESTADO_ABLACION.txt
# Parar: kill -TERM -<PGID> (el PGID está en ESTADO_ABLACION.txt); luego parar_sim.sh 87 y parar_sim.sh 88.
# Variables opcionales: OBJ_EXITOS (457), EST_EVAL (vla; «vla,ik_directa» añade el experto de 18 mm y duplica el tiempo),
#   SALTAR_ESPERA=1 (no esperar a que la WS esté libre), PASOS (40000), LOTE (32).
set -u
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; A_DIR=$V/ablacion_cobertura
E=$R/ESTADO_ABLACION.txt; cd $D
export HF_HOME=$D/hf_cache PYTHONIOENCODING=utf-8 VLA_HILOS=4
OBJ=${OBJ_EXITOS:-457}; OBJ_A=$(( (OBJ + 1) / 2 )); OBJ_B=$(( OBJ / 2 ))
PASOS=${PASOS:-40000}; LOTE=${LOTE:-32}; EST_EVAL=${EST_EVAL:-vla}
CA=$D/demos/crudas_cob18_a; CB=$D/demos/crudas_cob18_b; SEL=$D/demos/sel_cob18_457
DS=$D/demos/lerobot_cob18_mision; SAL=$V/entrenos/smolvla_cob18_mision_40k
MOD=$SAL/checkpoints/$(printf %06d $PASOS)/pretrained_model
CSV910=$R/eval_brazo_cob18_mision_s910.csv; CSV900=$R/eval_brazo_cob18_demo_s900.csv
estado() { echo "$(date '+%F %T') $*" >> $E; }
hecho() { grep -q "^.\{19\} HECHO $1\$" $E 2>/dev/null; }
marca() { estado "HECHO $1"; }
exitosos() { grep -l '"exito": true' $1/ep_*/meta.json 2>/dev/null | wc -l; }
cuantos() { ls -d $1/ep_* 2>/dev/null | wc -l; }
exito() { tail -n +2 $1 2>/dev/null | awk -F, -v e="${2:-}" '(e=="" || $4==e){s+=$5;n++} END {print s+0 "/" n+0}'; }
trap 'estado "INTERRUMPIDO (señal); relanzar el mismo comando para reanudar"; bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh 87 >/dev/null 2>&1; bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh 88 >/dev/null 2>&1; exit 1' INT TERM

# ---------- espera a que la WS esté libre: ni Gazebo ni Isaac ni otro entrenamiento/servidor VLA (de cualquier usuario)
esperar_libre() {   # $1 = etapa (solo para el registro)
  [ "${SALTAR_ESPERA:-0}" = 1 ] && return
  local n=0
  while true; do
    local ocup=$(pgrep -a -f '[i]gn gazebo|[g]z sim|[i]saac|[k]it/python|[l]erobot-train|[s]ervidor_politica' | cut -c1-80)
    local gpu=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)
    if [ -z "$ocup" ] && [ "${gpu:-0}" -lt 6000 ]; then return; fi
    [ $((n % 10)) -eq 0 ] && estado "esperando WS libre para $1: GPU ${gpu} MiB; procesos: $(echo "$ocup" | tr '\n' '|' | cut -c1-300)"
    n=$((n + 1)); sleep 60
  done
}

estado "INICIO ablación de cobertura (PGID $(ps -o pgid= -p $$ | tr -d ' ')): objetivo $OBJ éxitos, margen 18 mm, pinza 10 N·m al grabar, $PASOS pasos, lote $LOTE"

# ---------- 1) demostraciones
if ! hecho demos; then
  esperar_libre demos
  mkdir -p $CA $CB
  colector_exitos() {   # dominio particion carpeta objetivo_exitos semilla_base registro
    local DOM=$1 PART=$2 OUT=$3 OBJ1=$4 SB=$5 LOG=$6 k=0
    while [ $(exitosos $OUT) -lt $OBJ1 ] && [ $k -lt 15 ] && [ $(cuantos $OUT) -lt 600 ]; do
      local falta=$(( OBJ1 - $(exitosos $OUT) ))
      local n=$(( falta * 4 / 3 + 5 )); [ $n -gt 300 ] && n=300     # tasa de éxito esperada ~76 % (primera ronda a 10 N·m)
      estado "colector $DOM: tanda $((k + 1)), $(exitosos $OUT)/$OBJ1 éxitos en $(cuantos $OUT) episodios; grabo $n más"
      SO101_DISPOSICION=mision SO101_MARGEN=0.018 bash $A_DIR/colector_10Nm.sh $DOM $PART $OUT $n $((SB + 10 * k)) $LOG
      if [ $? -eq 5 ]; then estado "ERROR colector $DOM: la pinza no está a 10 N·m (ver $LOG)"; return 5; fi
      sleep 10; k=$((k + 1))
    done
    estado "colector $DOM terminado: $(exitosos $OUT) éxitos en $(cuantos $OUT) episodios ($OUT)"
  }
  colector_exitos 87 so101_foto $CA $OBJ_A 7100 $R/cob18_demos_a.log &
  sleep 60
  colector_exitos 88 so101_mision $CB $OBJ_B 8200 $R/cob18_demos_b.log &
  wait
  NA=$(exitosos $CA); NB=$(exitosos $CB)
  estado "demos: A $NA éxitos / $(cuantos $CA) episodios; B $NB / $(cuantos $CB)"
  if [ $((NA + NB)) -lt $OBJ ]; then estado "ERROR: solo $((NA + NB)) éxitos (< $OBJ); revisar los registros cob18_demos_*.log y relanzar"; exit 1; fi
  marca demos
fi

# ---------- 2) selección de exactamente OBJ episodios exitosos y conversión
if ! hecho conversion; then
  rm -rf $SEL; mkdir -p $SEL
  /usr/bin/python3 - "$CA" "$CB" "$SEL" $OBJ_A $OBJ_B <<'P'
import json, os, sys
ca, cb, sel, na, nb = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
def ok(c):
    return [os.path.join(c, d) for d in sorted(os.listdir(c)) if d.startswith('ep_') and os.path.exists(os.path.join(c, d, 'meta.json'))
            and json.load(open(os.path.join(c, d, 'meta.json')))['exito']]
A, B = ok(ca), ok(cb)
# si un colector se quedó corto, el otro completa
if len(A) < na: nb += na - len(A); na = len(A)
if len(B) < nb: na += nb - len(B); nb = len(B)
eps = A[:na] + B[:nb]; pos = {0: 0, 1: 0, 2: 0}
for i, d in enumerate(eps):
    os.symlink(d, os.path.join(sel, f'ep_{i:05d}'))
    m = json.load(open(os.path.join(d, 'meta.json'))); c = m['cubos']; y = c[m['color']][1]; o = [v[1] for k, v in c.items() if k != m['color']]
    pos[2 if all(v > y for v in o) else (0 if all(v < y for v in o) else 1)] += 1
print(f'{len(eps)} episodios seleccionados ({na} de A, {nb} de B); por posición izq/centro/der = {pos[0]}/{pos[1]}/{pos[2]}')
P
  estado "selección: $(ls $SEL | wc -l) episodios en $SEL"
  env/bin/python $V/convertir_demos_lerobot.py --crudas $SEL --salida $DS > $R/cob18_convertir.log 2>&1
  cod=$?; estado "conversión (código $cod): $(tail -1 $R/cob18_convertir.log)"
  [ $cod -eq 0 ] || exit 1
  marca conversion
fi

# ---------- 3) entrenamiento (sin simulaciones)
if ! hecho entreno; then
  if [ ! -d $MOD ]; then
    esperar_libre entreno
    bash $V/monitor_recursos.sh $R/consumo_cob18.csv & MON=$!
    if [ -d $SAL/checkpoints/last/pretrained_model ]; then
      estado "reanudo el ajuste desde $(readlink -f $SAL/checkpoints/last)"
      env/bin/lerobot-train --config_path=$SAL/checkpoints/last/pretrained_model/train_config.json --resume=true >> $R/cob18_entreno.log 2>&1
      cod=$?
      if [ $cod -ne 0 ]; then
        estado "la reanudación falló (código $cod): guardo el parcial y empiezo de cero"
        mv $SAL ${SAL}_parcial_$(date +%m%d%H%M); mv $R/cob18_entreno.log $R/cob18_entreno.log.parcial_$(date +%m%d%H%M)
      fi
    elif [ -d $SAL ]; then
      mv $SAL ${SAL}_parcial_$(date +%m%d%H%M)
    fi
    if [ ! -d $MOD ]; then
      estado "ajuste SmolVLA $PASOS pasos, lote $LOTE (receta de smolvla_escena_40k)"
      CAM2=scene bash $V/entrenar.sh $DS local/so101_cob18_mision $SAL $PASOS $LOTE $R/cob18_entreno.log
      estado "ajuste terminado (código $?)"
    fi
    kill $MON 2>/dev/null
  fi
  [ -d $MOD ] || { estado "ERROR: no hay modelo en $MOD"; exit 1; }
  marca entreno
fi

# ---------- 4) evaluación con la pinza a 2 N·m (sin overlay), dos simulaciones con su propio servidor de política
if ! hecho evaluacion; then
  esperar_libre evaluacion
  ( SO101_MARGEN=0.018 SO101_DISPOSICION=mision SEMILLA=910 VLA_PUERTO=5555 bash $V/evaluar_semilla.sh $MOD 50 $EST_EVAL $CSV910 \
      $V/intentos_vla_escena/eval_cob18_mision_s910 $R/cob18_mision_s910.log 87 so101_foto
    estado "banco misión s910: VLA cob18 $(exito $CSV910 vla) [40k 29/50, v2 49/50]" ) &
  sleep 60
  ( SO101_MARGEN=0.018 SO101_DISPOSICION=demo SEMILLA=900 VLA_PUERTO=5556 bash $V/evaluar_semilla.sh $MOD 50 $EST_EVAL $CSV900 \
      $V/intentos_vla_escena/eval_cob18_demo_s900 $R/cob18_demo_s900.log 88 so101_mision
    estado "banco demo s900: VLA cob18 $(exito $CSV900 vla) [40k 36/50, v2 47/50]" ) &
  wait
  N910=$(tail -n +2 $CSV910 2>/dev/null | awk -F, '$4=="vla"' | wc -l); N900=$(tail -n +2 $CSV900 2>/dev/null | awk -F, '$4=="vla"' | wc -l)
  if [ "$N910" -lt 50 ] || [ "$N900" -lt 50 ]; then estado "ERROR: evaluación incompleta (s910 $N910/50, s900 $N900/50); relanzar para completar"; exit 1; fi
  marca evaluacion
fi

# ---------- 5) resumen por posición
/usr/bin/python3 $A_DIR/resumen_ablacion.py $R > $R/cob18_resumen.txt 2>&1
estado "resumen: $(grep '^s910 cob18' $R/cob18_resumen.txt | head -1)"
marca resumen
estado "FIN ablación de cobertura (detalle en $R/cob18_resumen.txt)"
