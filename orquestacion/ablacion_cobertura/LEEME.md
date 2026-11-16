# Ablación de cobertura (preparada el 16-nov-2026, NO lanzada)

**Estado: preparada y comprobada en seco. No lanzar sin el OK del autor.**

## Pregunta

SmolVLA 40k (457 demostraciones con el pedido siempre al centro, margen 18 mm, pinza 10 N·m al grabar) recoge 0/18 en el extremo derecho; SmolVLA v2 (590 demostraciones con las tres posiciones, margen 26 mm, pinza 2 N·m al grabar, 30 000 pasos) recoge 19/19. La v2 cambió tres cosas a la vez. Esta ablación cambia **solo la cobertura**: la misma receta del 40k, pero con demostraciones con el pedido a la izquierda, al centro o a la derecha (`SO101_DISPOSICION=mision`).

| | SmolVLA 40k | **Ablación «cob18»** | SmolVLA v2 |
|---|---|---|---|
| Disposición de las demostraciones | pedido al centro | **izq./centro/der.** | izq./centro/der. |
| Margen del experto | 18 mm | **18 mm** (`SO101_MARGEN=0.018`) | 26 mm |
| Pinza al grabar | 10 N·m | **10 N·m** (overlay `overlays/pinza_10Nm`) | 2 N·m |
| Demostraciones exitosas | 457 (de 600) | **457** (exactas) | 590 |
| Ajuste | 40 000 pasos, lote 32 | **40 000 pasos, lote 32** | 30 000 pasos, lote 32 |
| Cámaras | muñeca → camera1, escena → camera2, 1 vacía | igual | igual |
| Acción | estado siguiente (sin «pinza = orden») | igual | igual |
| Evaluación | pinza 2 N·m | pinza 2 N·m | pinza 2 N·m |

Receta comprobada en `vla/entrenos/smolvla_escena_40k/checkpoints/040000/pretrained_model/train_config.json`: `lerobot/smolvla_base`, lote 32, 40 000 pasos, semilla 1000, `chunk_size` = `n_action_steps` = 50, lr 1e-4, calentamiento 1000, decaimiento 30 000, imágenes 256×256 con relleno a 512, `empty_cameras=1`. El orquestador llama al mismo `vla/entrenar.sh` con `CAM2=scene` que usó `noche3_entreno40k.sh`.

## Archivos (WS: `~/proyecto/paper_rover_vla_2025/vla/ablacion_cobertura/`)

- `ablacion_cobertura.sh`: orquestador. Etapas: demostraciones → conversión → ajuste → evaluación → resumen. Escribe `vla/registros/ESTADO_ABLACION.txt` con una línea `HECHO <etapa>` al terminar cada una; si se relanza, salta las hechas (las demostraciones también se reanudan por cuenta de éxitos; la evaluación, por escenas ya escritas en el CSV; el ajuste intenta `--resume=true` desde `checkpoints/last` y, si falla, guarda el parcial y empieza de cero).
- `colector_10Nm.sh`: copia de `vla/colector.sh` que carga el overlay de 10 N·m y **lee el `robot_description` de la simulación ya lanzada**: si la pinza no tiene `effort="10"`, no graba y sale con código 5 (el orquestador se detiene).
- `resumen_ablacion.py`: éxito por posición en s910 y total en s900, frente a 40k, ACT y v2 en las mismas escenas (IC de Wilson y McNemar exacto pareado). Solo biblioteca estándar.

## Qué hace cada etapa

1. **Demostraciones** (2 simulaciones en paralelo, dominios 87/`so101_foto` y 88/`so101_mision`, sin entrenamiento a la vez): `so101_demos.py` con `SO101_DISPOSICION=mision SO101_MARGEN=0.018`, pinza 10 N·m, semillas nuevas 7100+ y 8200+ (las de la v2 eran 5100+ y 6200+). Cada colector graba hasta 229 y 228 éxitos (tope 600 episodios por colector). Salida: `demos/crudas_cob18_a`, `demos/crudas_cob18_b`.
2. **Conversión**: elige exactamente 457 episodios exitosos (enlaces simbólicos en `demos/sel_cob18_457`, registra cuántos hay por posición) y los convierte con `vla/convertir_demos_lerobot.py` sin `--pinza-orden` → `demos/lerobot_cob18_mision`.
3. **Ajuste** (sin simulaciones; espera a que no haya Gazebo, Isaac, otro `lerobot-train` ni servidores VLA y a que la GPU use < 6 GB): `entrenar.sh` → `vla/entrenos/smolvla_cob18_mision_40k` (~24 GB de puntos de control).
4. **Evaluación** con la pinza a 2 N·m (instalación actual, sin overlay), dos simulaciones a la vez, cada una con su servidor de política (`VLA_HILOS=4`):
   - s910, disposición de misión, dominio 87, puerto 5555 → `registros/eval_brazo_cob18_mision_s910.csv`, intentos en `intentos_vla_escena/eval_cob18_mision_s910/`;
   - s900, disposición de demostración, dominio 88, puerto 5556 → `registros/eval_brazo_cob18_demo_s900.csv`, intentos en `intentos_vla_escena/eval_cob18_demo_s900/`.
   `SO101_MARGEN=0.018` (solo afecta al experto; el 40k en s910 se evaluó con el valor por defecto, que también es 18 mm). Por defecto solo `vla`; `EST_EVAL=vla,ik_directa` añade el experto y duplica el tiempo.
5. **Resumen**: `registros/cob18_resumen.txt`.

## Lanzamiento (solo con el OK del autor)

```bash
nohup setsid bash ~/proyecto/paper_rover_vla_2025/vla/ablacion_cobertura/ablacion_cobertura.sh \
  > ~/proyecto/paper_rover_vla_2025/vla/registros/ablacion_cobertura.out 2>&1 < /dev/null &
```

- Seguimiento: `cat ~/proyecto/paper_rover_vla_2025/vla/registros/ESTADO_ABLACION.txt`.
- Parar: `kill -TERM -<PGID>` (el PGID está en la primera línea de `ESTADO_ABLACION.txt`); después `bash ~/ros2_ws/src/paper_rover_vla_2025/tools/parar_sim.sh 87` y `... 88`. Nunca el dominio 77.
- Reanudar: el mismo comando de lanzamiento.

## Duración estimada (a partir de los registros reales)

| Etapa | Referencia medida | Estimación |
|---|---|---|
| Demostraciones | 1.ª ronda (10 N·m, 18 mm, pedido al centro): 600 episodios → 457 éxitos en 4 h 14 min (12-nov, 14:35-18:49, 2 colectores). v2 (2 N·m): 600 episodios en 4 h 53 min (15-nov, 04:13-09:06) | 4.5-6 h (≈ 600-700 episodios si el éxito del experto a 10 N·m con vecinos a un lado baja del 76 %) |
| Conversión | 457 episodios en 44 min (12-nov); 590 en 57 min (15-nov) | ≈ 45 min |
| Ajuste 40 000 pasos | `smolvla_escena_40k`: 5 h 41 min a 1.96 pasos/s (13-nov); v2 30 000 pasos: 4 h 33 min | ≈ 5 h 45 min |
| Evaluación s910 + s900 en paralelo (solo VLA) | 40k en s910 solo: 64 min (15-nov, 16:43-17:47); v2 con VLA + experto, 2 simulaciones: 2 h 05 min | ≈ 1 h 15 min (≈ 2 h 10 min con el experto) |
| Resumen | — | < 1 min |
| **Total** | | **≈ 12-14 h** (más la espera si la WS está ocupada) |

## Requisitos

- WS libre: sin Gazebo de otras sesiones, sin Isaac Sim, sin otro entrenamiento ni servidor VLA (el orquestador espera solo, salvo `SALTAR_ESPERA=1`). Máximo 2 simulaciones sin entrenamiento, y ninguna durante el ajuste (regla de carga del 14-nov).
- GPU libre durante el ajuste y la evaluación (no evaluar mientras se entrena: duplica la latencia de inferencia, problema del 13-nov).
- Disco: ~0.4 GB de demostraciones, ~0.4 GB de dataset y ~24 GB de puntos de control; hay ~395 GB libres (16-nov).
- Dominios 87 y 88 libres (son los mismos que usó `paso2_4.sh`; no se toca el 77).

## Riesgos

- **Tasa de éxito del experto a 10 N·m en disposición de misión:** desconocida. En la 1.ª ronda fue 76 % con el pedido al centro; con 10 N·m la pinza genera fuerzas espurias (banco del 16-nov) y con los vecinos a un solo lado podría bajar. Si los dos colectores llegan a 600 episodios sin 457 éxitos, el orquestador se detiene con un ERROR y hay que decidir (subir el tope o aceptar menos demostraciones).
- **Sesgo de selección distinto entre posiciones:** si el experto a 10 N·m falla más en un extremo, las 457 exitosas no tendrán un tercio por posición. La conversión registra el reparto en `ESTADO_ABLACION.txt`; hay que mirarlo antes de interpretar.
- **El código de grabación no es el del 12-nov:** `so101_demos.py`/`so101_trial.py` actuales (con las correcciones del 13-15-nov) y el overlay solo cambian el URDF de la pinza. La comparación limpia es con la v2 (mismo código, distinta receta) y, con esa salvedad, con el 40k.
- **Reanudación del ajuste:** `--resume=true` de LeRobot no se ha probado en esta WS; si falla, el orquestador guarda el parcial y empieza de cero (pierde las horas hechas).
- **Espera indefinida:** si hay un Gazebo/Isaac ajeno o la GPU está por encima de 6 GB (p. ej. Blender del autor con mucha memoria), el orquestador espera y lo registra cada 10 min; `SALTAR_ESPERA=1` lo evita bajo responsabilidad del que lanza.
- **Ruido de evaluación:** 18 escenas por extremo en s910; un IC de Wilson de 18 casos es ancho (p. ej. 3/18 → 6-39 %). Sirve para distinguir «recupera la derecha» de «sigue en ~0», no diferencias finas.

## Comprobaciones en seco hechas (16-nov)

- `bash -n` de `ablacion_cobertura.sh` y `colector_10Nm.sh`: sin errores; `resumen_ablacion.py` compila y, corrido sobre los registros actuales, reproduce 40k 13/14, 13/18, 3/18 (29/50) y v2 14/14, 18/18, 17/18 (49/50) en s910.
- Existen todas las rutas que usa (`env/bin/python`, `env/bin/lerobot-train`, `entrenar.sh`, `convertir_demos_lerobot.py`, `evaluar_semilla.sh`, `monitor_recursos.sh`, `banco_video/limite_pinza.py`, overlay, `parar_sim.sh`, `ros_env.sh`, `hf_cache`) y **no** existen aún las de salida (sin choque con nada previo).
- Disco: 395 GB libres.
- URDF por `xacro` sin lanzar Gazebo: con el overlay, `ros2 pkg prefix` = `overlays/pinza_10Nm/install/...` y la pinza da `<limit effort="10" .../>`; con la instalación actual, `effort="2.0"`. El overlay solo difiere de `colcon/install` en el URDF (diff de ficheros).
- Nada se lanzó: ni simulaciones, ni servidores, ni demostraciones, ni entrenamientos.
