# Guía de la versión 2: TurtleBot3 + SO-101 (+ VLA)

Robot diferencial TurtleBot3 Waffle Pi con un brazo SO-101 (LeRobot) en Gazebo Fortress + ROS 2 Humble.
**Flujo de la misión:** ir con Nav2 a la zona de recojo → acercarse con la cámara → recoger el cubo pedido (hoy el experto clásico, después el VLA) → ir con Nav2 a la zona de depósito → dejarlo en el plato.

```
 INICIO ──Nav2──▶ RECOJO ──ACERCAR──▶ RECOGER ──Nav2──▶ ENTREGA ──▶ COLOCAR ──▶ FIN
 (0,0)          (2.0, 1.5)  cámara de   /so101/pick     (2.0,-1.5)  /so101/place
                            muñeca      (hold=true)                 (sobre el plato)
```

---

## 1. Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Todo lo de ROS (paquetes, launch, config, scripts) | `~/ros2_ws/src/paper_rover_vla_2025/` |
| Paquete v2 | `paper_vla_tb3so101/` (`launch/`, `config/`, `urdf/`, `worlds/`, `maps/`, `scripts/`) |
| Interfaces (acción `Pick`) | `paper_vla_interfaces/action/Pick.action` |
| Datos (CSV de ensayos y misiones) | `~/ros2_ws/src/paper_rover_vla_2025/datos/` |
| Bitácora de decisiones y problemas | `docs/DECISIONES.md` |
| VLA / LeRobot (código propio, Python 3.12) | `~/proyecto/paper_rover_vla_2025/` |
| Compilación (build/install) | `~/proyecto/paper_rover_vla_2025/colcon/` |

## 2. Preparar cada terminal

```bash
source ~/proyecto/paper_rover_vla_2025/ros_env.sh     # ROS Humble + el paquete; quita conda; dominio 77, partición paper_vla
```
`ros_env.sh` aísla la simulación (`ROS_DOMAIN_ID=77`, `IGN_PARTITION=paper_vla`). Para correr **otra** simulación en paralelo, en sus terminales cambia ambos:
`export ROS_DOMAIN_ID=85 IGN_PARTITION=so101_prueba GZ_PARTITION=so101_prueba` (las dos variables; con una sola se mezclan).

Recompilar tras cambiar algo:
```bash
cd ~/proyecto/paper_rover_vla_2025/colcon && source /opt/ros/humble/setup.bash
colcon build --base-paths ~/ros2_ws/src/paper_rover_vla_2025 --build-base build --install-base install \
  --packages-select paper_vla_interfaces paper_vla_tb3so101
```

**Si algo se queda congelado** (Gazebo colgado, nodos que no mueren, «more than one action server»):
```bash
bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh        # para todo ROS 2 + Gazebo de TU dominio (77)
bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh 85     # otro dominio
```
Solo toca procesos de tu usuario y de ese dominio (no las simulaciones de otros): Ctrl-C, luego TERM y, si siguen colgados, KILL. `--todo` para todo el usuario (cuidado: también las otras simulaciones).

## 3. Los launch files (`paper_vla_tb3so101/launch/`)

| Launch | Qué levanta | Cuándo usarlo |
|---|---|---|
| `sim.launch.py` | Gazebo + mundo + robot + controladores (brazo, pinza) + puente ROS-Gazebo | solo ver el robot / mover el brazo a mano |
| `nav.launch.py` | `sim.launch.py` + Nav2 (mapa, AMCL, planificador, controlador `controller:=mppi\|dwb\|rpp\|mision`) | navegación |
| `manipulation.launch.py` | servidor del brazo `so101_manipulator` (acción `/so101/pick`, servicios) | sobre una simulación ya lanzada |
| **`cinematica.launch.py`** | **todo junto**: sim (o nav con `nav:=true`) + servidor del brazo + RViz (`rviz:=true`) | **lo normal** |

Argumentos de `cinematica.launch.py`: `headless` (false), `nav` (false), `controller` (mppi), `strategy` (ik_directa), `rviz` (false).

## 4. Recetas completas (2 terminales)

### 4.1 Misión completa (recoger y entregar)
```bash
# Terminal 1: mundo + robot + Nav2 + brazo + RViz   (esperar ~30 s a que Nav2 quede activo)
ros2 launch paper_vla_tb3so101 cinematica.launch.py nav:=true controller:=mision rviz:=true
# Terminal 2: N misiones; cada una escribe una fila en el CSV
ros2 run paper_vla_tb3so101 so101_mision.py --n 3 --out ~/ros2_ws/src/paper_rover_vla_2025/datos/misiones_$(date +%F).csv
```
Opciones de `so101_mision.py`: `--n`, `--out`, `--color rojo|verde|azul|azar` (el cubo que se pide; `azar` = uno distinto por misión), `--seed` (orden de los cubos y color al azar), `--ubicaciones archivo.yaml`, `--no-reponer` (no recolocar antes de la 1.ª), `--volver` (regresar a `inicio` al final).
En la zona de recojo hay **3 cubos (rojo, verde, azul)** separados 10 cm; antes de cada misión el script **repone** el escenario: robot a `inicio`, cubos **barajados** en la zona de recojo (el robot debe guiarse por el color, no por la posición) y pose inicial a AMCL.
Ejemplo: `ros2 run paper_vla_tb3so101 so101_mision.py --n 1 --color rojo` → imprime `PEDIDO: "quiero el cubo rojo"`, se acerca a ese cubo, lo recoge y lo lleva al plato.

### 4.2 Solo el brazo: ensayos de agarre (sin Nav2)
```bash
ros2 launch paper_vla_tb3so101 cinematica.launch.py                          # Terminal 1
ros2 run paper_vla_tb3so101 so101_pick_client.py --strategy ik_directa --n 5 --seed 11 --out ~/pick.csv   # Terminal 2
```
El cliente pone el cubo al azar a 13–19 cm delante, pide `/so101/pick` y anota éxito, altura del cubo y error de la cámara.
Comparar las 3 estrategias con el banco original (mismas posiciones para todas): `ros2 run paper_vla_tb3so101 so101_trial.py --strategy all --n 10 --seed 11 --out ~/agarres.csv`.

### 4.3 Órdenes sueltas al brazo (con la simulación lanzada)
```bash
ros2 action send_goal /so101/pick paper_vla_interfaces/action/Pick "{strategy: 'servovisual', color: 'rojo', hold: true}" --feedback
ros2 service call /so101/locate paper_vla_interfaces/srv/Locate "{color: 'azul'}"   # dónde ve el cubo azul (x, y)
ros2 service call /so101/place   std_srvs/srv/Trigger    # deja el cubo sujeto 16 cm delante
ros2 service call /so101/observe std_srvs/srv/Trigger    # pose de observación, pinza abierta
ros2 service call /so101/release std_srvs/srv/Trigger    # abre la pinza
ros2 service call /so101/ver     std_srvs/srv/Trigger    # devuelve "x y" del cubo visto (m, base_footprint)
ros2 topic echo /so101/estado                            # etapa actual
```

### 4.4 Demostraciones para el VLA (datos de entrenamiento)
```bash
ros2 launch paper_vla_tb3so101 cinematica.launch.py headless:=true             # Terminal 1 (sin Nav2)
ros2 run paper_vla_tb3so101 so101_demos.py --n 200 --seed 1 \
   --out ~/proyecto/paper_rover_vla_2025/demos/crudas                   # Terminal 2
```
Cada episodio: 3 cubos barajados delante del robot (como tras el paso ACERCAR), instrucción en inglés al azar («pick up the red cube», «grab the blue cube»…), el experto recoge el cubo pedido y se graba a 10 Hz: `wrist.mp4`, `scene.mp4` (cámara de escena del mástil, desde el 12-nov), `front.mp4` (256×256), `estado.csv` (5 articulaciones + pinza) y `meta.json` (instrucción, color, éxito, poses).
Si Gazebo se congela, el episodio se corta a los 300 s de tiempo real y el programa sale con código 3 (volver a lanzar: continúa en el episodio siguiente). Si los cubos no quedan en su sitio tras 3 intentos, el episodio se salta.
Convertir a LeRobotDataset (Python 3.12 del proyecto, **fuera de ROS**):
```bash
~/proyecto/paper_rover_vla_2025/env/bin/python ~/proyecto/paper_rover_vla_2025/vla/convertir_demos_lerobot.py \
   --crudas ~/proyecto/paper_rover_vla_2025/demos/crudas --salida ~/proyecto/paper_rover_vla_2025/demos/lerobot_so101_cubos
```
La acción de cada paso es la pose articular del paso siguiente; solo se usan los episodios con éxito.

Ajuste de SmolVLA (GPU RTX 5080; **avisar antes en la workstation compartida**). `lerobot/smolvla_base` ya espera el formato SO-101 (estado 6, acción 6, cámaras 256×256 llamadas camera1..3); nuestras cámaras se renombran:
```bash
cd ~/proyecto/paper_rover_vla_2025 && HF_HOME=$PWD/hf_cache env/bin/lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id=local/so101_cubos_colores --dataset.root=$PWD/demos/lerobot_so101_cubos \
  --rename_map='{"observation.images.wrist": "observation.images.camera1", "observation.images.scene": "observation.images.camera2"}' \
  --dataset.video_backend=pyav --policy.empty_cameras=1 --batch_size=32 --steps=20000 --save_freq=2000 \
  --output_dir=$PWD/vla/entrenos/smolvla_so101_cubos --policy.push_to_hub=false --wandb.enable=false
```
(Lo mismo hace `bash vla/entrenar.sh <dataset> <repo_id> <salida> <pasos> <lote> <registro>`; con datasets anteriores al 12-nov, que no tienen escena, usar `CAM2=front`.)

**Cámaras del VLA (desde el 12-nov):** muñeca (`/camera/image_raw` de la pinza) + **escena** (`/scene_camera/image_raw`, en un mástil en el lateral izquierdo de la base, a 0.41 m, mirando a la zona de los cubos). La frontal ya no entra al VLA: no ve los cubos (ver DOCUMENTACION_TRANSFERENCIA_V2.md §7.1).

**Probar el modelo en el brazo** (3 terminales):
```bash
# T0 (sin ROS): servidor de la política en la GPU
cd ~/proyecto/paper_rover_vla_2025 && HF_HOME=$PWD/hf_cache env/bin/python vla/servidor_politica.py \n   --modelo vla/entrenos/<entreno>/checkpoints/<paso>/pretrained_model
# T1: simulación y servidor del brazo
ros2 launch paper_vla_tb3so101 cinematica.launch.py
# T2: (opcional) grabar cada intento y luego el banco pareado VLA contra experto
ros2 param set /so101_manipulator vla_grabar_dir ~/proyecto/paper_rover_vla_2025/vla/intentos_vla
ros2 run paper_vla_tb3so101 so101_eval_brazo.py --n 10 --seed 900 --estrategias vla,ik_directa --out ~/eval_brazo.csv
ros2 action send_goal /so101/pick paper_vla_interfaces/action/Pick "{strategy: 'vla', color: 'rojo'}" --feedback   # un solo intento
```
Cada intento grabado tiene `wrist.mp4`, `scene.mp4`, `front.mp4`, `estado.csv`, `acciones.csv` (estado y acción pedida en cada paso) y `meta.json`.

### 4.5 Solo navegación
```bash
ros2 launch paper_vla_tb3so101 cinematica.launch.py nav:=true rviz:=true
```
En RViz: «2D Goal Pose» para mandar metas a mano. Desde terminal:
`ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "{pose: {header: {frame_id: map}, pose: {position: {x: 2.0, y: -1.5}, orientation: {w: 1.0}}}}"`

### 4.6 Grabar ubicaciones nuevas
Lleva el robot al sitio (RViz «2D Goal Pose» o teleop) y:
```bash
ros2 run paper_vla_tb3so101 guardar_ubicacion.py recojo_rojo --archivo ~/ubicaciones.yaml
ros2 run paper_vla_tb3so101 so101_mision.py --ubicaciones ~/ubicaciones.yaml
```
Las de fábrica están en `config/ubicaciones.yaml` (`inicio`, `recojo`, `entrega`). El cubo se coloca 16 cm delante de `recojo` y el plato está 16 cm delante de `entrega` (`config/arena.yaml` → `scripts/make_arena.py` regenera mundo y mapa).

### 4.7 VLA: corridas automáticas y diagnóstico (desde el 12-nov)
Todo se lanza desde `~/proyecto/paper_rover_vla_2025` y **cada corrida en su propio dominio** (85 evaluación, 87 pruebas, 88 misiones; el 77 es el manual). No hace falta `source ros_env.sh`: los scripts lo hacen solos. Si algo se congela, se recuperan solos; para cortarlos a mano: `bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh <dominio>` y `kill <PID>` del script.

**Evaluación pareada VLA contra experto** (mismas escenas para las dos estrategias; reanudable):
```bash
cd ~/proyecto/paper_rover_vla_2025
M=vla/entrenos/smolvla_escena_definitivo_1933/checkpoints/020000/pretrained_model
bash vla/evaluar.sh $M 20 vla,ik_directa vla/registros/eval_prueba.csv vla/intentos_vla_escena/prueba vla/registros/eval_prueba.log 87 so101_foto
#   NACC=10 bash vla/evaluar.sh ...   -> el VLA vuelve a decidir cada 10 acciones en vez de 25
#   Si el CSV ya tiene escenas, continúa desde la siguiente (para ampliar de 20 a 50 basta con volver a llamarlo con 50)
```
**Tanda de misiones completas** (Nav2 + brazo) con el experto o con el VLA:
```bash
bash vla/mision.sh ik_directa - 20 21 vla/registros/mis_experto.csv vla/intentos_mision/experto vla/registros/mis_experto.log 88 so101_mision
bash vla/mision.sh vla $M 20 21 vla/registros/mis_vla.csv vla/intentos_mision/vla vla/registros/mis_vla.log 88 so101_mision
```
**Orquestadores** (dejan todo encadenado; se siguen por sus archivos de estado):
| Script | Qué hace | Seguimiento |
|---|---|---|
| `vla/orquestador_escena.sh` | 2 colectores × 300 demostraciones → ajuste temprano → ajuste definitivo → evaluación | `vla/registros/ESTADO_ESCENA.txt` |
| `vla/orquestador_noche2.sh` | misiones experto (mientras se entrena) → evaluación ampliada a 50 → misiones con VLA | `vla/registros/ESTADO_NOCHE2.txt`, resumen en `RESUMEN_NOCHE2.txt` |
Lanzar uno sin que muera al cerrar la terminal: `setsid nohup bash vla/<orquestador>.sh > vla/registros/<orquestador>.out 2>&1 < /dev/null &`

**Diagnóstico de un intento VLA** (qué vio y qué hizo):
```bash
python3 vla/analizar_intento.py vla/intentos_vla_escena/<carpeta>/<intento> demos/crudas_escena_a /tmp/analisis
#  -> /tmp/analisis_fotogramas.jpg (muñeca y escena cada 3 s) y /tmp/analisis_articulaciones.png (estado y acción del VLA frente al experto)
```
**Comprobar que el canal del VLA puede reproducir una demostración** (hacerlo antes de entrenar si se cambia algo del canal):
```bash
# con una simulación lanzada (cinematica.launch.py) en el dominio de la terminal
/usr/bin/python3 ~/proyecto/paper_rover_vla_2025/colcon/install/paper_vla_tb3so101/lib/paper_vla_tb3so101/so101_replay.py    demos/crudas_escena_b/ep_00297 1 bin      # «bin» = pinza binaria, como el puente VLA; sin «bin» = pinza tal cual (0/6)
```
**Ver el consumo de recursos:** `tail vla/registros/consumo_escena.csv` (CPU, RAM, GPU, VRAM, potencia, temperatura cada 30 s).

## 5. Parámetros para aprender y ajustar

| Qué | Dónde | Valor | Efecto |
|---|---|---|---|
| Inclinación de la pinza al agarrar | `scripts/so101_trial.py` `PHI` | 80° | casi vertical; con menos no alcanza el suelo |
| Desplazamiento lateral del agarre | `MARGEN` | 0.018 m | **muy sensible**: ±1 mm cambia 5/5 a 1/5 |
| Profundidad de las almohadillas | `D_PROF` | 0.016 m | las mordazas se enfrentan 1.6 cm detrás de la punta |
| Apertura de la pinza | `GRIP_OPEN` | 0.85 rad | |
| Altura de levantado | `Z_LIFT` | 0.17 m | el cubo queda bajo el plano del LiDAR (0.19 m) |
| Distancia del cubo al robot | `so101_mision.py` `DELANTE` | 0.16 m | el acercamiento deja el cubo aquí |
| Radio del plato | `PLATO_R` | 0.10 m | criterio de entrega correcta |
| Tolerancia de llegada Nav2 | `config/nav2_mision.yaml` `xy/yaw_goal_tolerance` | 0.12 m / 0.3 rad | Nav2 se para ~14 cm antes; en la entrega lo corrige `afinar()` |
| Fuerza de la pinza | `urdf/so101.urdf.xacro`, `gripper` `<limit effort>` | **2.0 N·m** (14-nov; antes 10) | con 10 el robot patinaba con cubo lateral (problema 31); `max_effort` del controlador se ignora |
| Acercamiento fino en la entrega | `so101_mision.py` `afinar()` | activo (`--sin-afinar` lo quita) | lleva el robot a la meta con la pose de AMCL antes de colocar |
| Rango mínimo del LiDAR | `urdf/tb3_so101_fortress.urdf.xacro` `lidar_range_min` | 0.20 m | por debajo se ve el propio brazo |
| AMCL | `config/nav2_mision.yaml` `amcl:` | alpha1 0.4, alpha2 0.3, alpha3-5 0.1, recovery_alpha_fast 0.1, update 0.05 | 14-nov (A2); antes alpha 0.08 y recovery 0 (con 0.02 invertía el rumbo 180°) |

Tras cambiar un `.py`, `.yaml` o `.xacro`: recompilar (sección 2).

## 6. Datos que se guardan

**Misión** (`so101_mision.py`, una fila por misión): `exito`, `etapa_fallo` (nav_recojo, recoger, nav_entrega, colocar), tiempos y éxito por etapa (`nav1_*`, `pick_*`, `nav2_*`, `place_*`), `nav*_err_mm` (error real de llegada), `cubo_sujeto` (seguía sujeto al llegar), `cubo_err_plato_mm` (distancia del cubo al centro del plato), `total_s` (segundos de simulación).
**Agarre** (`so101_trial.py`): estimación de la cámara y su error, error del TCP, éxito, altura final del cubo, tiempos y carga de CPU.
La verdad de terreno de Gazebo (`/gt_tf`) se usa **solo para medir**; el robot decide con su cámara, su odometría y AMCL.

## 7. Problemas conocidos y su solución

| Síntoma | Causa | Solución aplicada |
|---|---|---|
| Nav2: «Starting point in lethal space», «Collision Ahead»; el robot no sale | Con el brazo adelantado el robot cabeceaba 8.6° y el LiDAR tocaba el suelo | rueda loca delantera en el xacro (cabeceo 0°) |
| AMCL con 20 cm o más de error | ruedas patinando + parámetros genéricos | AMCL afinado en `nav2_mision.yaml` (~4 cm) |
| Obstáculos pegados al robot al agarrar | el brazo pasa a 5–12 cm del LiDAR | `lidar_range_min` 0.20 m |
| El cubo queda en el borde del alcance | Nav2 llega con ~10 cm de error | paso ACERCAR con la cámara de muñeca |
| «more than one action server for /so101/pick» | quedó un servidor de otra corrida | cerrar todo con Ctrl-C; revisar `ps aux \| grep so101_manip_server` |
| Nav2 no se activa al arrancar | condición de carrera al iniciar | relanzar |
| Muchos «no detectado desde observación» tras varios episodios | el robot deriva ~1.5 cm y 4-5° por agarre | demostraciones y evaluación devuelven el robot a su pose y colocan los cubos respecto a él |
| «el grabador no arrancó» | proceso nuevo por episodio que a veces no descubría la simulación | grabador persistente (un proceso por corrida) |
| El VLA hace la secuencia pero el cubo no sube | la acción de la pinza era la posición medida (sin fuerza) | pinza binaria en `so101_vla.py` (comprobado con `so101_replay.py`: 0/6 → 6/6) |
| Una tanda se queda parada sin error | Gazebo congelado | colectores, `evaluar.sh` y `mision.sh` lo detectan (registro sin avanzar) y relanzan solos |
| AMCL se pierde por metros al llevar el cubo; el cubo cae fuera del plato | pinza con 10 N·m: con cubo lateral el robot patinaba solo | pinza a 2 N·m + `afinar()` (14-nov; experto 15 % → 90 %) |
| Orquestador colgado para siempre sin error | `wait` sin argumentos esperaba al monitor de recursos | `wait $P1 $P2` con PID |

## 8. Estado (14-nov-2026, 10:00)
- Configuración A7e2 en el paquete principal: pinza 2 N·m, AMCL A2, acercamiento fino en la entrega.
- Misiones completas: experto 90 % (103/115), VLA 40k 55 % (47/85). Brazo con 2 N·m (50 escenas): VLA 36/50 (72 %), experto 44/50 (88 %).
- Recetas nuevas: banco de la pinza `tools/prueba_sujecion.py <csv> cerrar azul,verde` (con `cinematica.launch.py` lanzado); misiones con configuración superpuesta y puerto VLA propio: `OVERLAY=<install> VIDEO=<dir> VLA_PUERTO=5556 bash vla/mision_overlay2.sh ...`; evaluación del brazo con configuración superpuesta: `OVERLAY=<install> bash vla/evaluar_overlay.sh ...`; resumen con IC: `python3 vla/resumen_noche14.py`.

### Estado del 12-nov (20:00)
- Cámara de escena en un mástil (el VLA usa muñeca + escena). 600 demostraciones nuevas, 457 exitosas.
- Corregidos: deriva del robot entre episodios, grabador persistente, vigilancia/reanudación en evaluación y misiones, **pinza binaria** en el puente VLA.
- En la noche: ajuste definitivo (457 episodios, 20 000 pasos), evaluación pareada (20 → 50 escenas), 20 misiones con el experto y 20 con el VLA (semilla 21). Ver `vla/registros/RESUMEN_NOCHE2.txt`.
- Detalle completo: `DOCUMENTACION_TRANSFERENCIA_V2.md`.

### Estado a media tarde (12-nov)
- Servidor del VLA y puente ROS funcionando; primer SmolVLA (muñeca + frontal, 8000 pasos) 0/5 contra 3/5 del experto → cámara de escena en mástil y nueva ronda de datos (`vla/orquestador_escena.sh`, estado en `vla/registros/ESTADO_ESCENA.txt`).

### Estado anterior (11-nov-2026)
- Brazo solo (experto clásico, n=10, orientativo): ik_directa 9/10, multietapa 8/10, servovisual 8/10.
- Misión completa: 2/2 en la primera prueba; tanda de 10 en `datos/` (ver DECISIONES.md).
- Falta: cubos de 3 colores + orden de color en `Pick`, demostraciones en formato LeRobot, ajuste de SmolVLA, servidor del VLA en el paso RECOGER.
