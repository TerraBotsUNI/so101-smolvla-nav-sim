#!/bin/bash
# Registra cada 30 s el consumo de la workstation en CSV (para el informe): carga, CPU, RAM, GPU, VRAM, potencia, temperatura,
# número de simulaciones Gazebo y si hay un entrenamiento corriendo. Uso: bash monitor_recursos.sh <archivo.csv>
OUT=$1
[ -f "$OUT" ] || echo "fecha,carga_1min,cpu_pct,ram_usada_gb,ram_total_gb,gpu_pct,vram_mib,vram_total_mib,gpu_w,gpu_c,sims_gazebo,entrenando" > "$OUT"
read -r _ a b c d e f g _ < /proc/stat; prev_tot=$((a+b+c+d+e+f+g)); prev_idle=$((d+e))
while true; do
  sleep 30
  read -r _ a b c d e f g _ < /proc/stat; tot=$((a+b+c+d+e+f+g)); idle=$((d+e))
  cpu=$(( 100 * ( (tot-prev_tot) - (idle-prev_idle) ) / (tot-prev_tot) )); prev_tot=$tot; prev_idle=$idle
  carga=$(cut -d' ' -f1 /proc/loadavg)
  ram=$(free -m | awk '/Mem:/ {printf "%.1f,%.1f", $3/1024, $2/1024}')
  gpu=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu --format=csv,noheader,nounits | tr -d ' ')
  sims=$(pgrep -fc "^ign gazebo -r -s")
  entr=$(pgrep -fc "lerobot-train")
  echo "$(date '+%F %T'),$carga,$cpu,$ram,$gpu,$sims,$entr" >> "$OUT"
done
