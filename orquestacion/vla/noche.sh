#!/bin/bash
# Cadena nocturna (12/13-nov-2026): demostraciones del experto -> conversión a LeRobot -> ajuste de SmolVLA en la GPU.
# Cada paso escribe su registro en vla/registros/ y el estado en vla/registros/ESTADO_NOCHE.txt. Si un paso falla, no se lanzan los siguientes.
# Lanzar:  nohup setsid bash ${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}/vla/noche.sh > /dev/null 2>&1 &
# Parar:   bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh 85   (y matar el proceso de lerobot-train por su PID si ya entrena)
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}
N_EPIS=${N_EPIS:-250}; SEMILLA=${SEMILLA:-404}; PASOS=${PASOS:-20000}; LOTE=${LOTE:-32}
R=$D/vla/registros; E=$R/ESTADO_NOCHE.txt; mkdir -p $R
estado() { echo "$(date '+%F %T') $*" | tee -a $E; }
estado "INICIO cadena nocturna: $N_EPIS episodios (semilla $SEMILLA), $PASOS pasos de ajuste, lote $LOTE"

# 1. Demostraciones (Gazebo sin ventana, dominio 85; el script de corrida cierra la simulación al terminar)
estado "PASO 1: grabando demostraciones en demos/crudas"
# Si la grabación se corta antes de tiempo (p. ej. el grabador deja de recibir imágenes), se relanza la simulación desde cero
# y se continúa hasta completar los episodios (máx. 6 relanzamientos). Cada relanzamiento usa otra semilla.
for intento in 1 2 3 4 5 6; do
  tot=$(ls -d $D/demos/crudas/ep_* 2>/dev/null | wc -l); falta=$((N_EPIS - tot))
  [ $falta -le 0 ] && break
  estado "PASO 1, tanda $intento: faltan $falta episodios"
  N=$falta SEED=$((SEMILLA + intento)) TMAX=25200 OUT=$D/demos/crudas bash /tmp/so101_demos_run.sh >> $R/noche_1_demos.log 2>&1
  bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh 85 > /dev/null 2>&1; sleep 5
done
ok=$(grep -l '"exito": true' $D/demos/crudas/ep_*/meta.json 2>/dev/null | wc -l)
tot=$(ls -d $D/demos/crudas/ep_* 2>/dev/null | wc -l)
estado "PASO 1 terminado: $ok episodios exitosos de $tot grabados"
if [ "$ok" -lt 40 ]; then estado "ALTO: menos de 40 episodios exitosos; no se entrena"; exit 1; fi

# 2. Conversión a LeRobotDataset (Python 3.12 del proyecto)
estado "PASO 2: convirtiendo a LeRobot (demos/lerobot_so101_cubos)"
cd $D && HF_HOME=$D/hf_cache env/bin/python vla/convertir_demos_lerobot.py --crudas demos/crudas --salida demos/lerobot_so101_cubos --repo-id local/so101_cubos_colores > $R/noche_2_conversion.log 2>&1
if ! grep -q "^listo" $R/noche_2_conversion.log; then estado "ALTO: falló la conversión (ver noche_2_conversion.log)"; exit 2; fi
estado "PASO 2 terminado: $(grep '^listo' $R/noche_2_conversion.log)"

# 3. Ajuste de SmolVLA (GPU)
SAL=$D/vla/entrenos/smolvla_so101_cubos_$(date +%Y%m%d_%H%M)
estado "PASO 3: ajustando SmolVLA en la GPU -> $SAL"
cd $D && HF_HOME=$D/hf_cache env/bin/lerobot-train --policy.path=lerobot/smolvla_base \
  --dataset.repo_id=local/so101_cubos_colores --dataset.root=$D/demos/lerobot_so101_cubos \
  --rename_map='{"observation.images.wrist": "observation.images.camera1", "observation.images.front": "observation.images.camera2"}' \
  --policy.empty_cameras=1 --batch_size=$LOTE --steps=$PASOS --save_freq=5000 --log_freq=100 \
  --output_dir=$SAL --policy.push_to_hub=false --wandb.enable=false --policy.device=cuda --dataset.video_backend=pyav > $R/noche_3_entrenamiento.log 2>&1
cod=$?
if [ $cod -ne 0 ] && grep -qiE "out of memory|CUDA error" $R/noche_3_entrenamiento.log; then
  estado "PASO 3: sin memoria con lote $LOTE; reintento con lote 16"
  rm -rf $SAL; cd $D && HF_HOME=$D/hf_cache env/bin/lerobot-train --policy.path=lerobot/smolvla_base     --dataset.repo_id=local/so101_cubos_colores --dataset.root=$D/demos/lerobot_so101_cubos     --rename_map='{"observation.images.wrist": "observation.images.camera1", "observation.images.front": "observation.images.camera2"}'     --policy.empty_cameras=1 --batch_size=16 --steps=$PASOS --save_freq=5000 --log_freq=100     --output_dir=$SAL --policy.push_to_hub=false --wandb.enable=false --policy.device=cuda --dataset.video_backend=pyav > $R/noche_3_entrenamiento_lote16.log 2>&1
  cod=$?
fi
estado "PASO 3 terminado (código $cod). Checkpoints: $(ls $SAL/checkpoints 2>/dev/null | tr '\n' ' ')"
estado "FIN cadena nocturna"
