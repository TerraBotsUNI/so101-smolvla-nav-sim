#!/bin/bash
# Orquestador de la madrugada (12-nov-2026): aprovecha la workstation al máximo.
#   - Colector A (dominio 85): continúa la grabación que ya corría hasta 250 episodios en demos/crudas.
#   - Colector B (dominio 86): segunda simulación en paralelo, 200 episodios en demos/crudas_b.
#   - Entrenamiento temprano en la GPU en cuanto haya 120 episodios exitosos (8000 pasos).
#   - Entrenamiento definitivo con todos los episodios cuando terminen los colectores (20000 pasos).
#   - Monitor de consumo cada 30 s en vla/registros/consumo_noche.csv.
# Estado en vla/registros/ESTADO_NOCHE.txt. Parar: bash tools/parar_sim.sh 85 ; ... 86 ; y matar orquestador/lerobot-train por PID.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE.txt; mkdir -p $R
estado() { echo "$(date '+%F %T') $*" >> $E; }
exitosos() { cat $D/demos/crudas/ep_*/meta.json $D/demos/crudas_b/ep_*/meta.json 2>/dev/null | grep -c '"exito": true'; }
cuantos() { ls -d $1/ep_* 2>/dev/null | wc -l; }
estado "ORQUESTADOR: 2 colectores en paralelo + entrenamiento temprano y definitivo + monitor de consumo"

bash $V/monitor_recursos.sh $R/consumo_noche.csv & MON=$!

colector_resiliente() {   # dominio particion carpeta objetivo semilla_base registro
  local DOM=$1 PART=$2 OUT=$3 OBJ=$4 SB=$5 LOG=$6
  for k in 1 2 3 4 5 6; do
    while pgrep -f "/tmp/so101_demos_run.sh" > /dev/null && [ "$DOM" = 85 ]; do sleep 30; done   # A: deja terminar la corrida que ya estaba en marcha
    local falta=$((OBJ - $(cuantos $OUT))); [ $falta -le 0 ] && break
    estado "colector $DOM: tanda $k, faltan $falta episodios"
    bash $V/colector.sh $DOM $PART $OUT $falta $((SB + 10 * k)) $LOG; sleep 5
  done
  estado "colector $DOM terminado: $(cuantos $OUT) episodios en $OUT"
}
colector_resiliente 85 so101_prueba $D/demos/crudas 250 404 $R/noche_1_demos.log & CA=$!
colector_resiliente 86 so101_b $D/demos/crudas_b 200 707 $R/noche_1b_demos.log & CB=$!

# --- entrenamiento temprano (la GPU estaba parada mientras se graba)
while [ $(exitosos) -lt 120 ] && kill -0 $CA 2>/dev/null; do sleep 120; done
if [ $(exitosos) -ge 60 ]; then
  estado "TEMPRANO: $(exitosos) episodios exitosos -> conversión y ajuste de 8000 pasos"
  rm -rf $D/demos/lerobot_temprano
  cd $D && HF_HOME=$D/hf_cache env/bin/python $V/convertir_demos_lerobot.py --crudas demos/crudas demos/crudas_b --salida demos/lerobot_temprano --repo-id local/so101_temprano > $R/noche_2_conversion_temprano.log 2>&1
  if grep -q "^listo" $R/noche_2_conversion_temprano.log; then
    bash $V/entrenar.sh $D/demos/lerobot_temprano local/so101_temprano $V/entrenos/smolvla_temprano_$(date +%H%M) 8000 32 $R/noche_3_entrenamiento_temprano.log
    estado "TEMPRANO terminado (código $?)"
  else estado "TEMPRANO: falló la conversión"; fi
fi

# --- definitivo
wait $CA $CB
estado "COLECTORES terminados: $(exitosos) exitosos ($(cuantos $D/demos/crudas) + $(cuantos $D/demos/crudas_b) grabados)"
rm -rf $D/demos/lerobot_so101_cubos
cd $D && HF_HOME=$D/hf_cache env/bin/python $V/convertir_demos_lerobot.py --crudas demos/crudas demos/crudas_b --salida demos/lerobot_so101_cubos --repo-id local/so101_cubos_colores > $R/noche_2_conversion.log 2>&1
if grep -q "^listo" $R/noche_2_conversion.log; then
  estado "DEFINITIVO: $(grep '^listo' $R/noche_2_conversion.log) -> ajuste de 20000 pasos"
  bash $V/entrenar.sh $D/demos/lerobot_so101_cubos local/so101_cubos_colores $V/entrenos/smolvla_definitivo_$(date +%H%M) 20000 32 $R/noche_3_entrenamiento.log
  estado "DEFINITIVO terminado (código $?)"
else estado "DEFINITIVO: falló la conversión (ver noche_2_conversion.log)"; fi
kill $MON 2>/dev/null
estado "FIN orquestador"
