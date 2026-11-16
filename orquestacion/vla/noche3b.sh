#!/bin/bash
# Noche 3 (corregida 13-nov 00:10): esperar a que termine orquestador_noche2.sh (evaluación de 50 escenas + misiones con VLA) SIN compartir la GPU,
# luego repetir en limpio las escenas 25..35 de la evaluación del definitivo (se hicieron con la GPU compartida: inferencia 90 ms en vez de 40)
# y por último el ajuste de 40000 pasos. Estado en vla/registros/ESTADO_NOCHE3.txt.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_NOCHE3.txt
estado() { echo "$(date '+%F %T') $*" >> $E; }
estado "NOCHE 3b: espera fin de la noche 2 -> repetir escenas 25..35 en limpio -> ajuste 40k"
until grep -q "FIN orquestador noche 2" $R/ESTADO_NOCHE2.txt; do sleep 120; done
M=$V/entrenos/smolvla_escena_definitivo_1933/checkpoints/020000/pretrained_model
estado "repito escenas 25..35 (vla,ik_directa) sin la GPU compartida"
DESDE=25 bash $V/evaluar_tramo.sh $M 36 vla,ik_directa $R/eval_escena_definitivo_tramo25a35_limpio_2026-11-13.csv $V/intentos_vla_escena/definitivo_tramo25a35 $R/noche3_tramo.log 85 so101_prueba
estado "tramo terminado (código $?)"
CAM2=scene bash $V/entrenar.sh $D/demos/lerobot_escena local/so101_escena $V/entrenos/smolvla_escena_40k 40000 32 $R/noche3_entreno_40k.log
estado "ajuste 40k terminado (código $?)"
pkill -f "monitor_recursos.sh .*consumo_noche3"; estado "FIN noche 3"
