"""RESUMEN.txt del banco de pinza en video. Uso: python resumen.py <carpeta de casos> <salida.txt> caso1 caso2 ..."""
import csv, math, os, sys

R, OUT, CASOS = sys.argv[1], sys.argv[2], sys.argv[3:]


def caso_info(c):
    d = os.path.join(R, c)
    filas = {r['prueba']: r for r in csv.DictReader(open(os.path.join(d, 'resultado.csv'), encoding='utf-8'))}
    tr = list(csv.DictReader(open(os.path.join(d, 'traza.csv'), encoding='utf-8')))
    # deriva durante la subida del cubo y la espera (fases asentar+quieto y final del agarre con la pinza ya cerrada): yaw real sin orden
    ag = [r for r in tr if r['fase'] == 'agarre']
    i_cierre = next((k for k, r in enumerate(ag) if abs(float(r['pinza_rad']) - float(ag[-1]['pinza_rad'])) < 0.002), len(ag) - 1)
    yr0 = float(ag[i_cierre]['yaw_real_deg'])
    q = [r for r in tr if r['fase'] == 'quieto']
    yr1 = float(q[-1]['yaw_real_deg'])
    lim = [l for l in open(os.path.join(d, 'config.txt'), encoding='utf-8') if 'limite' in l]
    return dict(filas=filas, deriva_total=math.degrees(math.remainder(math.radians(yr1 - yr0), 2 * math.pi)),
                t_deriva=float(q[-1]['t_sim']) - float(ag[i_cierre]['t_sim']), lim=lim[0].strip() if lim else '?')


L = ['BANCO DE SUJECIÓN EN VIDEO (16-nov-2026): pinza del SO-101 a 10 N·m (URDF original) frente a 2 N·m (actual)',
     'Cubo agarrado: AZUL (lateral derecho, -13 cm). "con vecinos": cubo verde (centro) y rojo (+13 cm) en el suelo junto al azul;',
     '"sin vecinos": verde y rojo alejados a ~18 m. Simulación nueva por caso (cinematica.launch.py, sin Nav2), dominio 87.',
     'Protocolo (prueba_sujecion_video.py, igual que tools/prueba_sujecion.py): Pick ik_directa con hold -> pinza cerrada (orden 0.0);',
     'asentar 2 s y QUIETO 8 s (s de reloj; ~5.6 s de simulación) -> giro wz=-0.6 4 s -> giro+avance wz=+0.6 vx=0.12 4 s -> avance vx=0.15 4 s.',
     'Error = giro real (Gazebo, /gt_tf) - giro de odometría (lo que ordenó y "cree" el robot). Ideal: 0°.',
     '"deriva sin orden" = giro real desde que la pinza termina de cerrar hasta el final de QUIETO (robot sin ninguna orden de velocidad).', '']
hdr = f'{"caso":<16}{"pinza rad":>10}{"quieto 8s":>11}{"deriva s/orden":>16}{"err giro":>10}{"err giro+av":>13}{"err avance":>12}{"cubo z fin":>12}'
L += [hdr, '-' * len(hdr)]
for c in CASOS:
    i = caso_info(c); f = i['filas']; g = f['giro']
    L.append(f'{c:<16}{float(g["pinza_rad"]):>10.3f}{float(g["quieto_giro_real_deg"]):>+10.1f}°{i["deriva_total"]:>+9.1f}° en {i["t_deriva"]:>3.0f}s'
             f'{float(f["giro"]["dif_deg"]):>+9.1f}°{float(f["giro_avance"]["dif_deg"]):>+12.1f}°{float(f["avance"]["dif_deg"]):>+11.1f}°'
             f'{100 * float(f["avance"]["cubo_z_final"]):>9.1f} cm')
L += ['', 'Detalle (odometría -> real) por caso:']
for c in CASOS:
    i = caso_info(c); f = i['filas']
    L.append(f'  {c}: {i["lim"]}')
    for p in ('giro', 'giro_avance', 'avance'):
        r = f[p]; L.append(f'      {p:<12} odometría {float(r["giro_odom_deg"]):+7.1f}°  real {float(r["giro_real_deg"]):+7.1f}°  desplazamiento {float(r["desp_m"]):.3f} m')
L.append('')
L.append('10Nm_sin_2: el agarre se dio por bueno pero el cubo se escurrió de la pinza durante la subida (z fin 2 cm); sin cubo sujeto el robot gira')
L.append('  bien (errores < 1°). No cuenta como prueba de sujeción: se repitió como 10Nm_sin_3.')
L.append('Cubo z fin: altura del cubo azul al terminar el avance (14-15 cm = sigue en la pinza; 2 cm = en el suelo).')
open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
