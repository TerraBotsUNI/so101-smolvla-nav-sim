#!/bin/bash
# 15-nov madrugada: ACT como tercera política (línea base del paper de SmolVLA), con las MISMAS 457 demostraciones que SmolVLA 40k
# (dataset demos/lerobot_escena), bloques de 50 acciones como SmolVLA. GPU libre hasta el paso 3 de paso2_4.sh (~10:00): tope de 7 h y nice 10.
# Las simulaciones del barrido y de las demostraciones v2 no usan Nav2 ni inferencia VLA, así que no se contaminan.
D=${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}; V=$D/vla; R=$V/registros; E=$R/ESTADO_ACT.txt; cd $D; export HF_HOME=$D/hf_cache PYTHONIOENCODING=utf-8
echo "$(date '+%F %T') INICIO ajuste ACT (457 demostraciones, lote 32, 40000 pasos, bloque 50)" >> $E
timeout 25200 nice -n 10 env/bin/lerobot-train --policy.type=act --dataset.repo_id=local/so101_escena --dataset.root=$D/demos/lerobot_escena \
  --dataset.video_backend=pyav --policy.chunk_size=50 --policy.n_action_steps=50 --batch_size=32 --steps=40000 --save_freq=5000 --log_freq=200 \
  --num_workers=4 --output_dir=$V/entrenos/act_escena_40k --policy.device=cuda --policy.push_to_hub=false --wandb.enable=false > $R/madrugada_act.log 2>&1
echo "$(date '+%F %T') FIN ajuste ACT (código $?; 124 = tope de 7 h alcanzado; checkpoints en vla/entrenos/act_escena_40k/checkpoints)" >> $E
