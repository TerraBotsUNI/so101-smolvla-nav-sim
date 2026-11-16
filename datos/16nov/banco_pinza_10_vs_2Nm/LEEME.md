# Banco de sujeción de la pinza SO-101: 10 N·m frente a 2 N·m (16-nov-2026)

## Pregunta

Tras agarrar un cubo, el TurtleBot3 con el brazo SO-101 gira solo, sin que nadie se lo ordene. Se separan dos causas posibles:

- **(A)** Fuerzas de contacto espurias de Gazebo. Aparecen cuando la pinza aprieta con el límite de par del URDF original (10 N·m): las mordazas se hunden en el cubo hasta unos 0.27 rad, frente a los 0.50 rad de la superficie del cubo.
- **(B)** Choque de la base con los cubos vecinos que quedan en el suelo. Los cubos miden 4 cm y el LiDAR no los ve.

## Protocolo

- Cada caso usa una simulación nueva: `cinematica.launch.py headless:=true`, sin Nav2, con dominio ROS 87 y partición `so101_foto`.
- Para 10 N·m se superpone un paquete aparte (overlay `~/proyecto/paper_rover_vla_2025/overlays/pinza_10Nm/`). Es idéntico al instalado salvo en `effort="10"` de la articulación `gripper`. En el `config.txt` de cada caso se comprueba el límite efectivo leído de `/tb3_so101/robot_description`.
- Banco: `orquestacion/banco_pinza/prueba_sujecion_video.py`, copia de `tools/prueba_sujecion.py` con dos añadidos:
  - `--sin-vecinos`: deja solo el cubo azul en su sitio y aleja el verde y el rojo a unos 18 m.
  - `--traza`: guarda un CSV a 10 Hz.
- Se agarra siempre el cubo **azul**, el lateral derecho, que está 16 cm delante y 13 cm a la derecha. El agarre es `Pick ik_directa` con hold, y la pinza recibe la orden de cerrarse a 0.0.
- Después vienen estas fases: asentar, QUIETO, giro (wz = −0.6 durante 4 s), giro+avance (wz = +0.6 y vx = 0.12 durante 4 s) y avance (vx = 0.15 durante 4 s).
- Error = giro real (pose de Gazebo en `/gt_tf`) − giro según la odometría (lo que se ordenó). El ideal es 0°.
- La fase QUIETO dura 8 s de reloj, que equivalen a unos 5.6 s de simulación. La «deriva sin orden» es el giro real desde que la pinza termina de cerrarse hasta el final de QUIETO, con la base sin ninguna orden de velocidad.

## Resultados

| Caso | Pinza (rad) | Deriva sin orden | Error giro | Error giro+avance | Error avance | Cubo arriba |
|---|---|---|---|---|---|---|
| 10 N·m, con vecinos (corrida 1) | 0.270 | +22.5° | −15.3° | −133.3° | −4.6° | sí |
| 10 N·m, con vecinos (corrida 2) | 0.284 | +0.8° | +67.4° | −160.6° | −8.8° | sí |
| 10 N·m, sin vecinos (corrida 1) | 0.265 | +24.7° | +64.2° | −161.7° | −118.4° | sí |
| 10 N·m, sin vecinos (corrida 2)* | 0.238 | −2.0° | +0.5° | −0.5° | 0.0° | **no** (se escurrió) |
| 10 N·m, sin vecinos (corrida 3) | 0.307 | −3.2° | +2.8° | −176.5° | +2.7° | sí |
| 2 N·m, con vecinos | 0.496 | 0.0° | +0.6° | −6.7° | −0.9° | sí |
| 2 N·m, sin vecinos | 0.496 | 0.0° | +0.6° | −6.5° | −1.1° | sí |

\* En la corrida 2 sin vecinos, el agarre se dio por bueno pero el cubo se resbaló durante la subida. Sin el cubo en la pinza el robot gira bien, así que esa corrida no prueba la sujeción y se repitió como corrida 3. Aun así, es un control útil: con 10 N·m y **sin** cubo sujeto, no hay error.

## Conclusión

La causa es **(A)**: el apriete a 10 N·m dentro del cubo genera fuerzas espurias.

- Sin vecinos y con 10 N·m, los errores son igual de grandes o mayores que con vecinos: hasta −176° en giro+avance, y −118° en un avance que debía ser recto.
- Con 2 N·m, los vecinos en el suelo no producen error. Los ±0.6° de giro y el ≈ −6.5° de giro+avance son idénticos con y sin vecinos, y salen del deslizamiento normal de las ruedas.
- En dos de las corridas a 10 N·m el robot gira incluso **parado**: unos 22° en 11 s de simulación, con las ruedas quietas, porque la odometría marca 0°.
- A 10 N·m el resultado es irregular: el momento y la magnitud del giro cambian de una corrida a otra, aunque siempre hay algún tramo con un error de decenas de grados.
- La causa (B) puede sumarse en casos puntuales. En la corrida 2 con vecinos, el video muestra el cubo verde rozando el costado de la base durante el giro. Pero no hace falta para explicar el fenómeno, y con la pinza a 2 N·m no aparece.

## Archivos

- `banco_pinza_comparacion.mp4`: video comparativo de 115 s, con un tramo por caso en este orden: 10 con, 10 sin, 2 con, 2 sin, 10 con (corrida 2) y 10 sin (corrida 3).
  - Cada tramo muestra la cámara de escena (en el mástil, mira hacia la pinza y el suelo) y la cámara de muñeca, lado a lado.
  - Debajo hay una gráfica del yaw ordenado (odometría, discontinuo) frente al real (dorado), con un cursor y los valores al instante: fase, error, posición de la pinza y altura del cubo.
  - Cada tramo arranca 12 s antes del final del agarre, es decir, al cerrarse la pinza y subir el cubo. Se reproduce a 2× el tiempo de simulación.
  - Al final hay una lámina fija de 10 s con los 6 casos.
- `banco_pinza_giros.svg`: la misma gráfica en versión vectorial, con 6 paneles y fondo claro.
- `RESUMEN.txt`: tabla y detalle de odometría frente al giro real por caso, incluida la corrida descartada.
- `registro.log`: registro de las corridas en la WS.
- `casos/<caso>/`, con estos archivos:
  - `traza.csv`, a 10 Hz: t_sim, yaw_odom_deg, yaw_real_deg, x_real, y_real, cmd_wz, cmd_vx, fase, pinza_rad y cubo_z.
  - `resultado.csv` y `banco.out`: la salida del banco.
  - `config.txt`: el paquete usado y el límite efectivo de la pinza.
  - `scene.mp4`, `wrist.mp4` y `front.mp4`: los videos completos del grabador, a 5 fps de simulación y 480×480. La imagen de escena original es de 640×480 y está comprimida a cuadrado.
- `orquestacion/banco_pinza/` (en este repositorio; los videos `.mp4` no se incluyen), con estos archivos:
  - `prueba_sujecion_video.py`: el banco.
  - `correr_banco_video.sh`: el orquestador en la WS.
  - `limite_pinza.py`: lee el límite de la pinza en `robot_description`.
  - `armar_video.py`: video, lámina y SVG con ffmpeg y matplotlib.
  - `resumen.py`: genera `RESUMEN.txt`.

En la WS, todo está en `~/proyecto/paper_rover_vla_2025/vla/banco_video/`.
