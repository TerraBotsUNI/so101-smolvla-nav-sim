#!/bin/bash
# 15-nov: un ensayo de prueba por controlador (dominio 90) para validar la configuración antes de la tanda del 16-nov. Resultados en *_prueba.
V=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}/vla; R=$V/registros
for c in mppi dwb rpp; do bash $V/nav_batch_so101.sh $c 1 90 0; done
for c in mppi dwb rpp; do mv $R/nav_so101_$c.csv $R/nav_so101_${c}_prueba.csv 2>/dev/null; mv $R/nav_so101_$c.txt $R/nav_so101_${c}_prueba.txt 2>/dev/null; done
echo FIN > $R/prueba_nav_so101.fin
