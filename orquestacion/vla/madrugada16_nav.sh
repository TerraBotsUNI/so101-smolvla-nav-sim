#!/bin/bash
# 16-nov madrugada: comparación MPPI/DWB/RPP con el robot del SO-101, 30 ensayos por controlador, 2 simulaciones, sin entrenamiento.
# Espera a que terminen las misiones finales (noche15.sh). Probado el 15-nov con un ensayo por controlador (*_prueba): los tres llegan.
V=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}/vla; R=$V/registros; E=$R/ESTADO_NAV_SO101.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
until grep -q "FIN noche15" $R/ESTADO_NOCHE15.txt 2>/dev/null; do sleep 120; done
estado "INICIO comparación MPPI/DWB/RPP con el SO-101 (30 ensayos por controlador)"
( bash $V/nav_batch_so101.sh mppi 30 87 1; estado "MPPI terminado: $(tail -n +2 $R/nav_so101_mppi.csv | awk -F, '$4=="True"' | wc -l)/30 llegaron"
  bash $V/nav_batch_so101.sh rpp 15 87 1 ) &
sleep 60
( bash $V/nav_batch_so101.sh dwb 30 88 1; estado "DWB terminado: $(tail -n +2 $R/nav_so101_dwb.csv | awk -F, '$4=="True"' | wc -l)/30 llegaron"
  bash $V/nav_batch_so101.sh rpp 15 88 16 ) &
wait
estado "RPP terminado: $(tail -n +2 $R/nav_so101_rpp.csv | awk -F, '$4=="True"' | wc -l)/30 llegaron"
estado "FIN comparación MPPI/DWB/RPP"
