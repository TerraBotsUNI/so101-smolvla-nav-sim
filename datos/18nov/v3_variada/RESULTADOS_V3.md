# Tanda v3 «variada»: resultados (18-nov-2026)

Tanda autorizada por el autor el 16-nov. Corrió del 16-nov 22:20 al 18-nov 05:10. Datos copiados de la WS: `vla/v3_variada/registros/`.

## Receta

- 2001 demostraciones con el experto clásico (margen 26 mm, pinza 2 N·m), de las que 1966 fueron exitosas (98 %).
- Variedad respecto de la v2:
  - 0, 1 o 2 vecinos junto al cubo pedido;
  - error de llegada: ±3 cm lateral, ±2 cm de distancia y ±10° de giro de la fila;
  - perturbaciones DART en 1236 episodios.
- Entrenamiento: SmolVLA (`smolvla_base`) con 60 000 pasos y lote 32, con la cámara de la muñeca y la de la escena.

## Éxito del agarre (50 escenas por banco, IC de Wilson al 95 %)

| Banco | v3 | v2 | Experto 26 mm | 40k |
|---|---|---|---|---|
| s910 (misión) | 47/50 (84-98 %) | 49/50 (90-100 %) | 48/50 | 29/50 |
| s900 (demo) | 47/50 (84-98 %) | 47/50 (84-98 %) | 49/50 | — |
| s920 (variado, nuevo) | 47/50 (84-98 %) | 46/50 (81-97 %) | 50/50 | — |

### Prueba de McNemar

- v3 frente a v2:
  - s910: 1/3 escenas discordantes, p = 0.625;
  - s900: 2/2, p = 1;
  - s920: 3/2, p = 1.
- v3 frente a 40k en s910: 19/1 escenas discordantes, p = 4×10⁻⁵.

### s920 por posición del cubo pedido

| Política | Izquierda | Centro | Derecha | Solo |
|---|---|---|---|---|
| v3 | 15/18 | 10/10 | 17/17 | 5/5 |
| v2 | 16/18 | 10/10 | 15/17 | 5/5 |

## Conclusión

La v3 **no se distingue estadísticamente de la v2** en ninguno de los tres bancos. Tampoco se distingue del experto. La v2 ya generalizaba bien a escenas variadas (46/50 en s920), así que la variedad y DART adicionales no aportan una mejora medible con 50 escenas por banco. Ambas superan con claridad a la 40k.

Todos los fallos de la v3 son «no levantó el cubo». En una revisión preliminar de los 6 primeros fallos, 5 tenían el cubo girado unos 30° o más. Falta comparar contra los éxitos con cubos igual de girados.

## Recursos (RTX 5080, 16 GB)

| Etapa | Duración | GPU | VRAM | Potencia GPU | Energía GPU | CPU / RAM |
|---|---|---|---|---|---|---|
| Demostraciones (3 simulaciones) | ≈ 13.5 h | no medido | — | — | — | no medido |
| Conversión | 3.5 h | solo CPU | — | — | — | no medido |
| Entrenamiento 60k | 10.2 h | 82 % | 11.8 GB (pico 11.9) | 243 W (pico 279) | ≈ 2.5 kWh | 25 % / 15 GB (pico 16.4); T máx. 84 °C |
| Evaluación (3 simulaciones + 3 servidores VLA) | 3.5 h | 4 % | 3.0 GB (pico 4.9) | 42 W | ≈ 0.15 kWh | 34 % / 14 GB (pico 18.1) |

- Inferencia de SmolVLA v3 (150 intentos): mediana 17.1 ms, p95 18.4 ms y máximo 20.2 ms por llamada.
- Duración mediana de un intento: 36 s.
