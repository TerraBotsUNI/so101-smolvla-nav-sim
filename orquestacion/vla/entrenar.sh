#!/bin/bash
# Ajuste de SmolVLA sobre un LeRobotDataset. Uso: [CAM2=scene|front] bash entrenar.sh <dataset_dir> <repo_id> <salida> <pasos> <lote> <registro>
# Cámaras: muñeca -> camera1 y CAM2 -> camera2 (por defecto «scene», la cámara del mástil desde el 12-nov; «front» para el dataset anterior).
# Si falta memoria en la GPU con el lote pedido, reintenta con lote 16.
DS=$1; REPO=$2; SAL=$3; PASOS=$4; LOTE=$5; LOG=$6; CAM2=${CAM2:-scene}
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; cd $D; export HF_HOME=$D/hf_cache PYTHONIOENCODING=utf-8
correr() {
  env/bin/lerobot-train --policy.path=lerobot/smolvla_base --dataset.repo_id=$REPO --dataset.root=$DS --dataset.video_backend=pyav \
    --rename_map="{\"observation.images.wrist\": \"observation.images.camera1\", \"observation.images.$CAM2\": \"observation.images.camera2\"}" \
    --policy.empty_cameras=1 --batch_size=$1 --steps=$PASOS --save_freq=2000 --log_freq=100 \
    --output_dir=$SAL --policy.push_to_hub=false --wandb.enable=false --policy.device=cuda > $LOG 2>&1
}
correr $LOTE; cod=$?
if [ $cod -ne 0 ] && grep -qiE "out of memory|CUDA error" $LOG; then
  mv $LOG $LOG.oom; rm -rf $SAL; correr 16; cod=$?
fi
exit $cod
