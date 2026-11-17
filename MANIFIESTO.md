# Manifiesto de datos

Qué datos sostienen cada cifra del artículo, cómo se generaron, qué se excluyó y por qué, y qué artefactos grandes (datasets y checkpoints) existen fuera de este repositorio.

Convenciones:

- **Semilla**: semilla del generador aleatorio (`random.Random(seed)`) que fija colores pedidos, orden y poses de los cubos.
- **Escena pareada**: la misma escena (color pedido + disposición de los tres cubos) se repite idéntica para cada política; los scripts de análisis lo comprueban con `assert`.
- **Éxito en el banco del brazo**: cubo pedido a más de 8 cm de altura y junto a la pinza.
- **Éxito en misión**: cubo correcto dentro del plato de entrega (radio 10 cm).
- **Configuración A7e2**: pinza a 2 N·m en el URDF, AMCL con alpha1 0.4, alpha2 0.3, alpha3-5 0.1, recovery_alpha_fast 0.1 y slow 0.001, y acercamiento fino `afinar()` en la entrega. Todas las cifras finales del artículo usan A7e2.

## 1. Demostraciones (entrenamiento)

| Conjunto | Intentos grabados | Exitosos (entran al dataset) | Pasos (10 Hz de simulación) | Disposición | Pinza | Margen del experto | Semillas | Dataset LeRobot |
|---|---|---|---|---|---|---|---|---|
| **v1** (12-nov) | 600 (300 + 300) | 457 | 85 707 | demostración (pedido en el centro) | 10 N·m | 18 mm | colector A: 1110, 1120, …; colector B: 2210, 2220, … (base 1100 / 2200 + 10·tanda, `orquestacion/vla/orquestador_escena.sh`) | `demos/lerobot_escena` |
| v1 con la pinza reetiquetada (14-nov) | mismos 600 | 457 | 85 707 | ídem | ídem | ídem | ídem | `demos/lerobot_escena_pinzaorden` (`convertir_demos_lerobot.py --pinza-orden`) |
| **v2** (15-nov) | 600 (300 + 300) | 590 | 108 879 | misión (`SO101_DISPOSICION=mision`) | 2 N·m | 26 mm | colector A: **5100**; colector B: **6200** (un solo flujo de 300 episodios por colector, sin reintentos; `orquestacion/vla/paso2_4.sh`, campo `semilla` de cada `meta.json`) | `demos/lerobot_v2_mision` |

Cada episodio crudo contiene `wrist.mp4`, `scene.mp4`, `front.mp4` (256×256, 10 Hz de simulación), `estado.csv` (5 articulaciones + pinza) y `meta.json` (instrucción en inglés, color, éxito, motivo, poses de los cubos respecto al robot). La conversión (`orquestacion/vla/convertir_demos_lerobot.py`) toma solo los episodios exitosos, usa `observation.images.wrist`, `observation.images.scene`, `observation.state` (6) y `action[t] = estado[t+1]`.

## 2. Separación entrenamiento / prueba

La separación es **por semilla**: ninguna semilla de evaluación se usó para grabar demostraciones.

| Uso | Semillas |
|---|---|
| Demostraciones v1 | 1110-1300 y 2210-2400 (tandas de 10 en 10) |
| Demostraciones v2 | 5100 (colector A) y 6200 (colector B) |
| Banco del brazo, disposición de demostración | **900** (50 escenas) |
| Banco del brazo, disposición de misión | **910** (50 escenas; también el barrido del margen, 30 escenas) |
| Misiones completas (resultado final) | **21, 22, 23, 24** (20 misiones cada una) |
| Misiones del experto adicionales (cifra 148/160 de la v8) | 25, 28, 30, 32 |
| Banco clásico de las tres estrategias del experto | 11 (10 posiciones) |

Las poses de los cubos son continuas (posición y guiñada aleatorias), así que dos semillas distintas no generan la misma escena salvo coincidencia improbable.

## 3. Bancos de agarre pareados (prueba)

| Archivo (`datos/…`) | Semilla | Políticas | Notas |
|---|---|---|---|
| `14nov/eval_escena_definitivo_n50_FINAL_2026-11-13.csv` | 900 | SmolVLA 20k, experto 18 mm | pinza 10 N·m; tramo 25-35 repetido sin GPU compartida |
| `14nov/eval_escena_40k_n50_2026-11-13.csv` | 900 | SmolVLA 40k | pinza 10 N·m |
| `14nov/eval_brazo_A7e2_40k_n50_s900.csv` (= `16nov/…`) | 900 | SmolVLA 40k, experto 18 mm | A7e2 |
| `14nov/eval_brazo_A7e2_po40k_n50_s900.csv` | 900 | SmolVLA con pinza reetiquetada | A7e2 |
| `15nov/eval_brazo_A7e2_40k_nacc{10,15}_n50_s900.csv` | 900 | SmolVLA 40k con 10 y 15 acciones por inferencia | ablación |
| `15nov/paso1_experto_m{18,22,26,30}_r{0,3}_mision_s910.csv` | 910 | experto con margen 18-30 mm, sin ruido y con ruido ±3 mm/±10° | 30 escenas; margen elegido (26 mm) con un criterio fijado antes del barrido |
| `16nov/eval_brazo_v2_demo_s900.csv` | 900 | SmolVLA v2, experto 26 mm | |
| `16nov/eval_brazo_v2_mision_s910.csv` | 910 | SmolVLA v2, experto 26 mm | |
| `16nov/eval_brazo_40k_mision_s910.csv` | 910 | SmolVLA 40k | |
| `16nov/eval_brazo_act_{demo_s900,mision_s910}.csv` | 900 / 910 | ACT 40k | |

## 4. Misiones completas

| Archivos | Política | Semillas | Uso |
|---|---|---|---|
| `14nov/final_misiones_experto_A7e2_n20_s*.csv` | experto 18 mm | 21-25, 28, 30, 32 | 21-24 en la Tabla VII; las ocho en la cifra 148/160 |
| `14nov/final_misiones_vla40k_A7e2_n20_s2{1..4}.csv` | SmolVLA 40k | 21-24 | Tabla VII |
| `14nov/final_misiones_vlapo40k_A7e2_n20_s2{1..4}.csv` | SmolVLA, pinza reetiquetada | 21-24 | Tabla VII |
| `16nov/final_misiones_experto_m26_A7e2_n20_s2{1..4}.csv` | experto 26 mm | 21-24 | Tabla VII |
| `16nov/final_misiones_vlav2_A7e2_n20_s2{1..4}.csv` | SmolVLA v2 | 21-24 | Tabla VII |
| `11-12nov/*.csv` | experto, pruebas iniciales | 21 y otras | historia del desarrollo; no entran en las tablas finales |

## 5. Lotes excluidos por carga de CPU

Carpeta `datos/14nov/afectadas_carga_14nov/` (detalle en su `LEEME.txt`). Se excluyeron **por un criterio horario fijado antes de mirar los resultados**:

- experto s26-s29 y SmolVLA 40k s25-s28: corrieron el 14-nov desde las 09:56 con 3-4 simulaciones a la vez en 40 vCPU;
- experto s26 y s27 (parcial) de las 14:40: 2 simulaciones a la vez que el ajuste de SmolVLA.

Síntoma: Nav2 registra «Control loop missed its desired rate of 20.0000Hz» (hasta 261 avisos por simulación), «Optimizer fail» (MPPI) y «Collision Ahead»; carga 45-72, 50 % de CPU en el núcleo; los fallos de navegación al recojo se duplicaron (SmolVLA s28: 10 de 14). Desde entonces: máximo 2 simulaciones sin entrenamiento y 1 durante un entrenamiento. En las tandas válidas de la segunda ronda la relación entre avisos y fallos de navegación se informa como descriptiva (`cpu_*` en `res_v13.json`).

Otras exclusiones:

- navegación (16-nov): los ensayos en los que Nav2 no llegó a activarse en 180 s no se cuentan (2 de DWB, 4 de RPP; 3 de RPP se repusieron con los ensayos 31-33); consta en `datos/16nov/navegacion_so101/ESTADO_NAV_SO101.txt` y en las columnas de los `.txt`;
- `16nov/analisis_derecha/`: la misión SmolVLA v2 s22 se descartó del análisis de trayectorias (19 carpetas para 17 intentos esperados) y SmolVLA 40k s21/s24 no tienen intentos grabados.

## 6. Navegación (Tabla IX)

`datos/16nov/navegacion_so101/nav_so101_{mppi,dwb,rpp}.csv` (un ensayo por fila) y `.txt` (registro con la carga y los avisos de MPPI por ensayo). Meta (2.0, 1.5) m desde (0, 0, 0), parámetros por defecto de cada controlador, simulación nueva en cada ensayo; éxito = llegada informada y error planar real ≤ 0.30 m; la pose real (Gazebo) solo se usa para medir. Resumen: `resumen_nav_so101.json`, reproducible con `analisis/navegacion/analizar_nav.py`.

## 7. Banco de la pinza (10 frente a 2 N·m)

`datos/16nov/banco_pinza_10_vs_2Nm/`: 7 casos (`10Nm_con_1/2`, `10Nm_sin_1/2/3`, `2Nm_con_1`, `2Nm_sin_1`), con `traza.csv` a 10 Hz, `resultado.csv`, `banco.out`, `config.txt` y `RESUMEN.txt`. La variante de 10 N·m se obtiene con el parche `config/overlay_pinza_10Nm.patch`. Los videos (`scene.mp4`, `wrist.mp4`, `front.mp4` por caso y `banco_pinza_comparacion.mp4`) no se incluyen.

## 8. Checkpoints

Todos en la estación de trabajo, en `$PROYECTO/vla/entrenos/<entreno>/checkpoints/<paso>/pretrained_model`. Base: `lerobot/smolvla_base`; cámaras: muñeca → `camera1`, escena → `camera2`, `empty_cameras=1`; lote 32; checkpoint cada 2000 pasos.

| Nombre en el artículo | Carpeta | Dataset | Pasos | Checkpoint usado | SHA-256 de `model.safetensors` |
|---|---|---|---|---|---|
| SmolVLA temprano | `smolvla_escena_temprano_1639` | 154 episodios (muñeca + escena) | 8 000 | `008000` | `0e9d482772dcd316f316d0beccec3375a274679409e3b35abbc5d11177faea81` |
| SmolVLA 20k | `smolvla_escena_definitivo_1933` | `lerobot_escena` (457) | 20 000 | `020000` | `ec1ff712d08ef96f54cdda55fb872a3b084d761d0e8711ae332af3feac3056a8` |
| **SmolVLA 40k** | `smolvla_escena_40k` | `lerobot_escena` (457) | 40 000 | `040000` | `5ea4269b68e24744fb1c008ffb42ce0160194472ede602ba071ca2ff1870fc43` |
| SmolVLA, pinza reetiquetada | `smolvla_pinzaorden_40k` | `lerobot_escena_pinzaorden` (457) | 40 000 | `040000` | `98b29938f6c09eb0beeab769a30a99ff90fce3d5065447982aef246196fe0120` |
| **SmolVLA v2** | `smolvla_v2_mision_30k` | `lerobot_v2_mision` (590) | 30 000 | `030000` | `0b157fa15a1e93151d44f823874ef46f2f0f47887eb65d9d189e2d6175593050` |
| **ACT** | `act_escena_40k` | `lerobot_escena` (457) | 40 000 (bloque 50) | `040000` | `0d90f1fe817f6af9056c42decc910ff7f86d2814893553ccda997c2a8d93bcbc` |

Tamaño de `model.safetensors`: 906 712 520 bytes en cada SmolVLA y 206 494 928 bytes en ACT. Cada `pretrained_model` incluye además `config.json`, `train_config.json` y los procesadores de normalización (`policy_preprocessor*`, `policy_postprocessor*`). Comprobación: `sha256sum $PROYECTO/vla/entrenos/<entreno>/checkpoints/<paso>/pretrained_model/model.safetensors` (sumas calculadas en la WS el 16-nov-2026).

## 9. Datasets y artefactos grandes (no incluidos)

| Artefacto | Tamaño | Publicación propuesta |
|---|---|---|
| `demos/lerobot_escena` (457 episodios, 85 707 pasos) | 375 MiB | [COMPLETAR: p. ej. Hugging Face Datasets] |
| `demos/lerobot_escena_pinzaorden` | 374 MiB | [COMPLETAR] |
| `demos/lerobot_v2_mision` (590 episodios, 108 879 pasos) | 460 MiB | [COMPLETAR] |
| Episodios crudos (`demos/crudas_escena_{a,b}`, `demos/crudas_v2_{a,b}`) | 773 MiB en total (189 + 195 MiB v1; 195 + 194 MiB v2) | [COMPLETAR: opcional, Zenodo] |
| Checkpoints de la sección 8 | 4.5 GiB las seis carpetas `pretrained_model` | [COMPLETAR: p. ej. Hugging Face Models] |
| Grabaciones de cada intento de la política (`vla/intentos_*`) y videos de misión | ~1.0 GiB de intentos (`intentos_mision` 336 MiB, `intentos_vla_escena` 697 MiB, `intentos_vla` 1.2 MiB) y 1.3 GiB de videos de misión | [COMPLETAR] |

## 10. Archivos traídos de la estación de trabajo (16-nov-2026)

Esta versión incluye todos los archivos del paquete que solo estaban en la WS, copiados de la versión usada en el artículo (los tres scripts del experto y el conversor se tomaron del respaldo `antes_v3_2026-11-16`, previo a los cambios de la tanda posterior al artículo, que no se incluye):

- `ros2/paper_vla_tb3so101/launch/sim.launch.py`, `worlds/` (`paper_vla_arena.sdf`, `paper_vla_arena_vistas.sdf`, `paper_vla_empty.sdf`), `maps/paper_vla_arena.{yaml,pgm}` y `urdf/colores.xacro`;
- `ros2/paper_vla_tb3so101/meshes/so101/*.stl` (18 mallas de TheRobotStudio/SO-ARM100, 19 MiB; el URDF usa 13);
- `ros2/paper_vla_tb3so101/config/nav2_mppi.yaml`, `nav2_dwb.yaml`, `nav2_rpp.yaml` (generados por `scripts/make_nav2_params.py`) y `controllers.yaml`;
- `ros2/paper_vla_tb3so101/scripts/nav_trial.py`, `make_nav2_params.py`, `autotune.py`, `plot_trial.py` y `verificar_fk.py`;
- versiones del 15-nov de `so101_demos.py` (`SO101_DISPOSICION=mision`), `so101_eval_brazo.py` (`--disposicion`), `so101_trial.py` (`SO101_MARGEN`, `SO101_RUIDO_MM`, `SO101_RUIDO_DEG`), `config/arena.yaml` (cubos separados 0.13 m) y `CMakeLists.txt` (instala `so101_vla.py` y `so101_eval_brazo.py`);
- comparación de navegación (Tabla IX): `orquestacion/vla/madrugada16_nav.sh`, `nav_batch_so101.sh`, `prueba_nav_so101.sh` y `nav_so101/nav2_so101_{mppi,dwb,rpp}.yaml` (= `nav2_mision.yaml` salvo el bloque `controller_server`, con los parámetros por defecto de cada controlador);
- `orquestacion/vla/servidor_politica_gen.py`, `evaluar_gen.sh`, `evaluar_semilla.sh`, `paso1_margen.sh`, `paso2_4.sh`, `madrugada15.sh`, `madrugada_act.sh`, `manana15_experto26.sh`, `tarde15_act.sh`, `noche15.sh` y la versión con `--pinza-orden` de `convertir_demos_lerobot.py`;
- `orquestacion/ros_env.sh`: el original de la WS (sustituye a la reconstrucción anterior).

En todos se sustituyó la ruta del proyecto por `${PROYECTO:-$HOME/proyecto/paper_rover_vla_2025}` (o `~/proyecto/...` en comentarios) y los identificadores de Hugging Face por `local/...`; no hay otros cambios.

Sigue fuera del repositorio la dependencia `turtlebot3_manipulation` (ROBOTIS, Apache-2.0): clonar el repositorio oficial (versión para ROS 2 Humble) en el mismo workspace de `colcon`, porque el URDF incluye `$(find turtlebot3_manipulation_description)/urdf/turtlebot3_waffle_pi.urdf.xacro`.
