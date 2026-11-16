# Análisis por posición del cubo pedido: por qué falla la derecha y no la izquierda (16-nov-2026)

## Qué se midió

Para cada intento de recogida con trayectoria grabada (`acciones.csv`: estado medido de las 6 articulaciones y orden de pinza a 10 Hz) se tomó el **primer cierre de la pinza** (orden de pinza < 0.65) y se calculó, igual que en el diagnóstico del 15-nov (`analisis/diagnostico_posicion/comun.py` y `analisis5.py`):

- **Giro de muñeca al cerrar** = grados(`wrist_roll` medido − π/2). Es la misma magnitud que dio los +18.6 ± 4.3° del paper.
- **Centro de agarre** por cinemática directa invirtiendo la fórmula del experto (`tcp = centro + 16 mm·a − m·u`, con `u` el eje de apertura de la pinza, de la mordaza fija a la móvil).
- **Tipo de fallo** según la meseta de la pinza: `cierra_en_vacio` (meseta < 0.1), `sujeta_no_levanta`, `sujeta_y_pierde`, `oscila`, `nunca_cierra`.
- Solo en el banco s910 (donde se conoce la pose del cubo pedido):
  - **Error de giro** = giro medido − giro que usaría el experto para el yaw de ese cubo. La referencia del experto se ajustó con sus 400-y-pico demostraciones exitosas: giro ≈ 0.996·yaw + 4.2°.
  - **Error lateral `err_u`** = desplazamiento del centro de agarre respecto al cubo a lo largo de `u`, medido **respecto al agarre nominal de la receta de cada política** (m = 18 mm para 40k, «pinza = orden» y ACT; m = 26 mm para v2: a v2 se le suman 8 mm, si no saldría −6 mm en todas las posiciones solo por el cambio de receta). `err_u > 0` significa que el cubo queda desplazado hacia el lado de la **mordaza fija** (que está a solo m del centro del cubo); `err_u < 0`, hacia la **mordaza móvil**, que tiene ~28 mm de holgura. Con giro ~0, `+u` ≈ `+y` del robot (izquierda).

La posición en la fila se obtiene así: en misión, el índice del color pedido en `orden_cubos` (0 = izquierda, 1 = centro, 2 = derecha, misma convención que el diagnóstico); en el banco s910, con la `y` de los vecinos (los dos a la izquierda, `y` mayor ⇒ el pedido está en el extremo derecho).

## De dónde salen los datos (WS, `~/proyecto/paper_rover_vla_2025/vla/`)

| Fuente | Carpetas de intentos | CSV de resultados | Alineación |
|---|---|---|---|
| Misión SmolVLA 40k | `intentos_mision/final_vla40k_A7e2_s22`, `_s23` | `registros/final_misiones_vla40k_A7e2_n20_s2{1..4}.csv` | s22 y s23 sí; **s21 y s24 no tienen intentos grabados** (carpetas vacías) |
| Misión «pinza = orden» | `intentos_mision/final_vlapo40k_A7e2_s21..s24` | `final_misiones_vlapo40k_A7e2_n20_s2{1..4}.csv` | las 4 semillas |
| Misión SmolVLA v2 | `intentos_mision/final_vlav2_s21..s24` | `final_misiones_vlav2_A7e2_n20_s2{1..4}.csv` | s21, s23, s24; **s22 descartada** (19 carpetas para 17 intentos esperados) |
| Banco s910 (disposición de misión, 50 escenas, pinza 2 N·m) | `intentos_vla_escena/eval_40k_mision_s910`, `eval_act_mision_s910`, `eval_v2_mision_s910` | `registros/eval_brazo_{40k,act,v2}_mision_s910.csv` | 50/50 en las tres; colores verificados |
| Experto | — | filas `ik_directa` de `eval_brazo_v2_mision_s910.csv` | el experto **no graba trayectorias** (las carpetas `paso1_*` y `final_experto_*` están vacías): solo hay su resultado |

Cada intento de misión se asigna a su misión recorriendo, en orden temporal, las misiones que llegan a RECOGER y consumiendo `pick_intentos` carpetas por misión; se comprueba que el color de cada carpeta coincida (detalle en `alineacion_misiones.csv`). Las tablas usan solo el **primer intento** de cada misión.

## Resultados (primer intento)

| Fuente | Política | Posición | n | Éxitos | Giro de muñeca (°) media ± DE | Error de giro vs. experto, mediana (°) | Error lateral `err_u`, mediana (mm) | Fallos |
|---|---|---|---|---|---|---|---|---|
| Misión | 40k | izquierda | 12 | 11 | −15.1 ± 3.4 | — | — | 1 sujeta y pierde |
| Misión | 40k | centro | 14 | 10 | +0.8 ± 3.9 | — | — | 4 cierra en vacío |
| Misión | 40k | derecha | 6 | 0 | +17.5 ± 3.2 | — | — | 6 cierra en vacío |
| Misión | pinza = orden | izquierda | 28 | 26 | −13.9 ± 3.7 | — | — | 2 cierra en vacío |
| Misión | pinza = orden | centro | 25 | 17 | +0.1 ± 4.4 | — | — | 8 cierra en vacío |
| Misión | pinza = orden | derecha | 21 | 0 | +19.8 ± 5.0 | — | — | 21 cierra en vacío |
| Misión | v2 | izquierda | 20 | 20 | −16.7 ± 5.3 | — | — | — |
| Misión | v2 | centro | 17 | 17 | +3.3 ± 3.1 | — | — | — |
| Misión | v2 | derecha | 16 | 16 | +21.1 ± 4.6 | — | — | — |
| s910 | 40k | izquierda | 14 | 13 | (yaw al azar) | −2.6 | **−0.4** (media 0.0 ± 1.5) | 1 cierra en vacío |
| s910 | 40k | centro | 18 | 13 | | −1.1 | **+1.3** (1.5 ± 1.9) | 4 cierra en vacío, 1 sujeta sin levantar |
| s910 | 40k | derecha | 18 | 3 | | +1.8 | **+8.8** (16 de 18 > +3 mm; 4 a ~+95 mm, hacia el vecino) | 13 cierra en vacío, 2 sujeta y pierde |
| s910 | ACT | izquierda | 14 | 12 | | +5.2 | **−7.3** (−7.6 ± 4.0) | 2 sujeta sin levantar |
| s910 | ACT | centro | 18 | 13 | | −1.0 | −1.0 | 3 sujeta sin levantar, 1 vacío, 1 pierde |
| s910 | ACT | derecha | 18 | 2 | | +0.5 | **+8.3** | 15 cierra en vacío, 1 sujeta sin levantar |
| s910 | v2 | izquierda | 14 | 14 | | +1.1 | +1.8 | — |
| s910 | v2 | centro | 18 | 18 | | +0.9 | +1.8 | — |
| s910 | v2 | derecha | 18 | 17 | | +0.3 | +0.4 | 1 cierra en vacío |
| s910 | experto (ik_directa, m = 26 mm) | izq./centro/der. | 14/18/18 | 13/17/18 | — | — | — | — |

40k y «pinza = orden» juntas en misión: izquierda −14.3 ± 3.6° (37/40), centro +0.3 ± 4.2° (27/39), derecha **+19.2 ± 4.7°** (0/27, los 27 «cierra en vacío»). Difiere algo de las cifras del diagnóstico (88 intentos alineados: −15.4 ± 3.7°, +0.9°, +18.6 ± 4.3°) porque aquí se alinearon 106 primeros intentos; el patrón es el mismo.

**Tolerancia asimétrica de la pinza** (banco s910, las tres políticas juntas, `exito_por_error_lateral_s910.csv`): con `err_u` ≤ −4 mm (cubo hacia la mordaza móvil) recogen 14/16; entre −1 y +3 mm, 69/76; entre +3 y +6 mm, 6/15; entre +6 y +20 mm, 1/20; > +20 mm, 0/6. La pinza perdona varios milímetros hacia la mordaza móvil y casi nada (~3 mm) hacia la fija.

## Conclusión

1. **La izquierda sí se midió y sí gira la muñeca**: −14 a −15° (40k y «pinza = orden»), simétrico a los +18-20° de la derecha. La afirmación «la izquierda no se midió» no es correcta: la cifra estaba en `DIAGNOSTICO_VLA_FABLE_2026-11-15.md` §2.5 (−15.4 ± 3.7°).
2. **El giro de muñeca no es la causa del fallo.** Es la corrección correcta para la fila girada que ve el robot en los extremos: en el banco s910 el giro del 40k coincide con el del experto en las tres posiciones (mediana −2.6°, −1.1°, +1.8°), y SmolVLA v2 gira lo mismo en misión (+21.1° a la derecha) y recoge 16/16. Por tanto la frase del paper «la muñeca giró +18.6° (+0.9° en el centro) y todos cerraron en vacío» es cierta pero sugiere una causalidad que los datos no apoyan.
3. **Lo que distingue la derecha es un error lateral hacia la mordaza fija.** En el banco s910 (misma disposición que la misión, pose del cubo conocida) el 40k coloca la pinza con `err_u` mediano +8.8 mm a la derecha frente a −0.4 mm a la izquierda y +1.3 mm en el centro; ACT, entrenado con los mismos datos, igual (+8.3 mm). A la derecha `+u` apunta hacia los vecinos, de modo que la pinza se corre hacia ellos y la mordaza fija (a solo 18 mm del centro) cae sobre el cubo: «cierra en vacío».
4. **¿Por qué la izquierda no?** Dos efectos, medidos: (a) con el 40k el sesgo a la izquierda prácticamente no existe (−0.4 ± 1.5 mm); (b) cuando existe, como en ACT (−7.3 mm, también hacia los vecinos), cae del lado de la mordaza móvil, que tiene ~28 mm de holgura, y se recoge igual (12/14). Es decir: la hipótesis «el sesgo hacia los vecinos cae del lado que absorbe la holgura» se confirma para ACT; para el 40k la izquierda directamente no tiene sesgo. Por qué el 40k se desvía solo cuando los vecinos están a la izquierda no se puede saber con estos datos (las demostraciones nunca mostraron un extremo; es comportamiento fuera de distribución). [HIPÓTESIS]
5. **Límite:** en la misión no se registra la pose real del cubo respecto al robot, así que el error lateral en misión no se puede calcular; el mecanismo se mide en el banco s910, que reproduce la disposición de la misión. El experto no graba trayectorias, así que su giro en cada posición se estima con su relación giro-yaw de las demostraciones, no se mide en misión.

Frase propuesta para responder al revisor (orientativa, no está en el paper): «El giro de muñeca en los extremos (−15° a la izquierda, +19° a la derecha) es la corrección correcta de la fila girada y coincide con la del experto (±3°). Lo que falla a la derecha es la posición lateral: en el banco con la disposición de la misión, SmolVLA y ACT desplazan la pinza 8-9 mm hacia los cubos vecinos, que a la derecha es el lado de la mordaza fija (a 18 mm del centro), y cierran en vacío; a la izquierda el desplazamiento es nulo (SmolVLA) o cae del lado de la mordaza móvil, con ~28 mm de holgura (ACT, 12/14).»

## Archivos

- `intentos_por_posicion.csv`: un intento por fila (fuente, política, semilla, misión/escena, n.º de intento, posición, éxito, tipo, giro, referencia del experto, error de giro, `err_u_nominal`, errores x/y/u/n, pose del cubo, meseta de pinza, carpeta de origen). Errores en metros, giros en grados.
- `resumen_por_posicion.csv`: resumen por fuente, política y posición (primer intento).
- `exito_por_error_lateral_s910.csv`: éxito por tramo de error lateral.
- `alineacion_misiones.csv`: comprobación de la alineación intento-misión por tanda.
- `giro_muneca_por_posicion.svg` / `.pdf` / `.png`: (a) giro de muñeca en misión; (b) error de giro frente al experto en s910; (c) error lateral en s910. Puntos llenos = éxito, huecos = fallo; raya = mediana; los valores fuera de escala se dibujan en el borde.
- `consola.txt`: salida completa del análisis.
- `../../../analisis/analisis_derecha/` (en este repositorio): `analisis_derecha.py` (uso: `python analisis_derecha.py <raíz> <salida>`; la raíz debe contener `intentos_mision/`, `intentos_vla_escena/`, `registros/` y `demos_metricas.csv`), `figura_derecha.py` y `comun.py` (copia sin cambios del diagnóstico del 15-nov).
