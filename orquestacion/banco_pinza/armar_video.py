"""Arma el video comparativo del banco de pinza 10 N·m vs 2 N·m, la lámina final y la gráfica SVG de los giros.
Uso: python armar_video.py <carpeta de casos> <carpeta de salida> caso1 caso2 ...
Cada caso: <carpeta>/<caso>/{traza.csv, resultado.csv, video/{scene.mp4, wrist.mp4, estado.csv}}"""
import csv, os, shutil, subprocess, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

R, OUT, CASOS = sys.argv[1], sys.argv[2], sys.argv[3:]
TMP = os.path.join(R, '_tmp_video')
FUENTE = 'C\\:/Windows/Fonts/arialbd.ttf'
DORADO, GRAFITO, GRIS, AMARILLO, FONDO = '#CA8A04', '#1A1A1A', '#9CA3AF', '#FACC15', '#0E0E0E'
FPS_OUT = 10                      # el grabador graba 5 cuadros por segundo de simulación -> 2x (y 8x durante el agarre)
PREVIO = 12.0                     # se muestran los últimos 12 s del agarre (cierre de la pinza y subida del cubo)
W, HV, HT, HG = 960, 480, 60, 324
FASES = {'agarre': 'agarre (final)', 'asentar': 'asentar', 'quieto': 'quieto', 'giro': 'giro', 'giro_avance': 'giro+avance', 'avance': 'avance'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})


def ff(*a):
    subprocess.run(['ffmpeg', '-y', '-v', 'error', *a], check=True)


def rotulo(caso):
    p = caso.split('_')
    t = f'{p[0].replace("Nm", " N·m")}, {"con vecinos" if p[1] == "con" else "sin vecinos"}'
    return t + (f' (corrida {p[2]})' if len(p) > 2 and p[2] != '1' else '')


def leer_traza(d):
    rows = list(csv.DictReader(open(os.path.join(d, 'traza.csv'), encoding='utf-8')))
    t = np.array([float(r['t_sim']) for r in rows])
    yo = np.degrees(np.unwrap(np.radians([float(r['yaw_odom_deg']) for r in rows])))
    yr = np.degrees(np.unwrap(np.radians([float(r['yaw_real_deg']) for r in rows])))
    fase = [r['fase'] for r in rows]
    pz = np.array([float(r['pinza_rad']) for r in rows]); cz = np.array([float(r['cubo_z']) for r in rows])
    i0 = max(i for i, f in enumerate(fase) if f == 'agarre')
    i0 = int(np.searchsorted(t, t[i0] - PREVIO))                       # referencia: 12 s antes del fin del agarre (yaw a cero ahí)
    return dict(t=t - t[i0], t0=t[i0], yo=yo - yo[i0], yr=yr - yr[i0], fase=fase, pz=pz, cz=cz)


def tramos(tr):
    out, f0, ta = [], None, None
    for t, f in zip(tr['t'], tr['fase']):
        if f != f0:
            if f0 in FASES:
                out.append((f0, ta, t))
            f0, ta = f, t
    if f0 in FASES:
        out.append((f0, ta, tr['t'][-1]))
    return out


def ejes(ax, tr, oscuro, titulo=None):
    c_txt, c_odo, c_real, c_sombra = (('#E5E7EB', GRIS, AMARILLO, '#262626') if oscuro else (GRAFITO, GRAFITO, DORADO, '#F3F4F6'))
    tt = tramos(tr); x0 = tt[0][2] - PREVIO
    for k, (f, a, b) in enumerate(tt):
        if k % 2 == 0:
            ax.axvspan(a, b, color=c_sombra, lw=0, zorder=0)
        ax.text((max(a, x0) + b) / 2, 1.01 + 0.075 * (k % 2), FASES[f], transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=8.5, color=GRIS)
    m = (tr['t'] >= x0) & (tr['t'] <= tt[-1][2] + 0.5)
    ax.plot(tr['t'][m], tr['yo'][m], color=c_odo, lw=1.6, ls='--', label='yaw ordenado (odometría)')
    ax.plot(tr['t'][m], tr['yr'][m], color=c_real, lw=2.0, label='yaw real (Gazebo)')
    ax.set_xlim(x0, tt[-1][2] + 0.5)
    lo, hi = min(tr['yo'][m].min(), tr['yr'][m].min()), max(tr['yo'][m].max(), tr['yr'][m].max())
    ax.set_ylim(lo - 15, hi + 15)
    ax.set_ylabel('yaw (°)', color=c_txt); ax.set_xlabel('tiempo de simulación (s; 0 = 12 s antes de terminar el agarre)', color=c_txt)
    ax.tick_params(colors=c_txt)
    for s in ax.spines.values():
        s.set_color(GRIS)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.grid(axis='y', color=GRIS, alpha=0.25, lw=0.6)
    if titulo:
        ax.set_title(titulo, color=c_txt, fontsize=11.5, fontweight='bold', loc='left', pad=30)
    return tt


def segmento(caso, k):
    d = os.path.join(R, caso); tr = leer_traza(d)
    est = list(csv.DictReader(open(os.path.join(d, 'video', 'estado.csv'), encoding='utf-8')))
    tv = np.array([float(r['t_sim']) for r in est]) - tr['t0']
    tt = tramos(tr); ta, tb = tt[0][2] - PREVIO, tt[-1][2] + 0.5
    sel = [i for i, t in enumerate(tv) if ta <= t <= tb]
    td = os.path.join(TMP, caso); shutil.rmtree(td, ignore_errors=True)
    for cam in ('scene', 'wrist'):
        os.makedirs(os.path.join(td, cam + '_todo')); os.makedirs(os.path.join(td, cam))
        ff('-i', os.path.join(d, 'video', cam + '.mp4'), '-q:v', '2', '-start_number', '0', os.path.join(td, cam + '_todo', '%05d.jpg'))
        for j, i in enumerate(sel):
            shutil.copy(os.path.join(td, cam + '_todo', f'{i:05d}.jpg'), os.path.join(td, cam, f'{j:05d}.jpg'))
    # gráfica por cuadro: estática + cursor
    os.makedirs(os.path.join(td, 'graf'))
    fig = plt.figure(figsize=(W / 100, HG / 100), dpi=100, facecolor=FONDO)
    ax = fig.add_axes([0.075, 0.17, 0.62, 0.68], facecolor=FONDO)
    ejes(ax, tr, True)
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1.0), frameon=False, labelcolor='#E5E7EB', fontsize=9.5)
    cur = ax.axvline(0, color='#E5E7EB', lw=1.0)
    p_o, = ax.plot([], [], 'o', color=GRIS, ms=5); p_r, = ax.plot([], [], 'o', color=AMARILLO, ms=6)
    info = fig.text(0.715, 0.10, '', color='#E5E7EB', fontsize=10, va='bottom', family='DejaVu Sans Mono')
    for j, i in enumerate(sel):
        t = tv[i]; q = int(np.clip(np.searchsorted(tr['t'], t), 0, len(tr['t']) - 1))
        cur.set_xdata([t, t]); p_o.set_data([t], [tr['yo'][q]]); p_r.set_data([t], [tr['yr'][q]])
        info.set_text(f'fase   {FASES.get(tr["fase"][q], tr["fase"][q])}\nodom   {tr["yo"][q]:+7.1f}°\nreal   {tr["yr"][q]:+7.1f}°\n'
                      f'error  {tr["yr"][q] - tr["yo"][q]:+7.1f}°\npinza  {tr["pz"][q]:.3f} rad\ncubo z {100 * tr["cz"][q]:.1f} cm\nvel.   x2')
        fig.savefig(os.path.join(td, 'graf', f'{j:05d}.png'), facecolor=FONDO)
    plt.close(fig)
    rot = os.path.join(td, 'rotulo.txt'); open(rot, 'w', encoding='utf-8').write(f'Caso {k}  ·  pinza {rotulo(caso)}')
    sub = os.path.join(td, 'sub.txt'); open(sub, 'w', encoding='utf-8').write('cámara de escena (mástil)')
    sub2 = os.path.join(td, 'sub2.txt'); open(sub2, 'w', encoding='utf-8').write('cámara de muñeca')
    salida = os.path.join(TMP, f'seg_{k}.mp4')
    esc = lambda r: r.replace('\\', '/').replace(':', '\\:')
    rotp, subp, sub2p = esc(rot), esc(sub), esc(sub2)
    filtro = (f'[0:v]scale=480:480:flags=neighbor[a];[1:v]scale=480:480:flags=neighbor[b];[a][b]hstack=2[v];'
              f'[v]pad={W}:{HV + HT}:0:{HT}:color={FONDO},'
              f"drawtext=fontfile='{FUENTE}':textfile='{rotp}':fontcolor={AMARILLO}:fontsize=28:x=16:y=14,"
              f"drawtext=fontfile='{FUENTE}':textfile='{subp}':fontcolor=#E5E7EB@0.85:fontsize=14:x=12:y={HT + 8}:box=1:boxcolor=black@0.45:boxborderw=4,"
              f"drawtext=fontfile='{FUENTE}':textfile='{sub2p}':fontcolor=#E5E7EB@0.85:fontsize=14:x=492:y={HT + 8}:box=1:boxcolor=black@0.45:boxborderw=4[top];"
              f'[top][2:v]vstack=2,pad={W}:{HV + HT + HG}:0:0:color={FONDO},format=yuv420p[out]')
    ff('-framerate', str(FPS_OUT), '-i', os.path.join(td, 'scene', '%05d.jpg'), '-framerate', str(FPS_OUT), '-i', os.path.join(td, 'wrist', '%05d.jpg'),
       '-framerate', str(FPS_OUT), '-i', os.path.join(td, 'graf', '%05d.png'), '-filter_complex', filtro, '-map', '[out]',
       '-c:v', 'libx264', '-crf', '20', '-r', str(FPS_OUT), salida)
    return salida, tr


def lamina(trs, ruta_png, ruta_svg):
    n = len(trs); filas = (n + 1) // 2
    for oscuro, ruta in ((True, ruta_png), (False, ruta_svg)):
        fig, axs = plt.subplots(filas, 2, figsize=(9.6 if oscuro else 11, (HV + HT + HG) / 100 if oscuro else 3.4 * filas),
                                dpi=100, facecolor=FONDO if oscuro else 'white', squeeze=False)
        for ax, (caso, tr) in zip(axs.flat, trs):
            ax.set_facecolor(FONDO if oscuro else 'white')
            ejes(ax, tr, oscuro, rotulo(caso))
            ax.xaxis.label.set_size(8.5); ax.yaxis.label.set_size(9); ax.tick_params(labelsize=8.5)
        for ax in list(axs.flat)[n:]:
            ax.axis('off')
        h, l = axs.flat[0].get_legend_handles_labels()
        fig.legend(h, l, loc='lower center', ncol=2, frameon=False, labelcolor='#E5E7EB' if oscuro else GRAFITO, fontsize=10)
        fig.suptitle('Banco de sujeción SO-101 (cubo azul, lateral derecho)\nyaw ordenado por odometría frente a yaw real en Gazebo',
                     color=AMARILLO if oscuro else GRAFITO, fontsize=12, fontweight='bold')
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        fig.savefig(ruta, facecolor=fig.get_facecolor())
        if not oscuro:
            fig.savefig(os.path.join(TMP, 'lamina_clara.png'), facecolor='white')
        plt.close(fig)


os.makedirs(TMP, exist_ok=True); os.makedirs(OUT, exist_ok=True)
segs, trs = [], []
for k, caso in enumerate(CASOS, 1):
    s, tr = segmento(caso, k); segs.append(s); trs.append((caso, tr)); print('segmento', k, caso, flush=True)
png = os.path.join(TMP, 'lamina.png')
lamina(trs, png, os.path.join(OUT, 'banco_pinza_giros.svg'))
lam = os.path.join(TMP, 'seg_lamina.mp4')
ff('-loop', '1', '-framerate', str(FPS_OUT), '-t', '10', '-i', png, '-vf', f'scale={W}:{HV + HT + HG},format=yuv420p', '-c:v', 'libx264', '-crf', '20', '-r', str(FPS_OUT), lam)
lista = os.path.join(TMP, 'lista.txt')
open(lista, 'w').write(''.join(f"file '{os.path.abspath(s).replace(chr(92), '/')}'\n" for s in segs + [lam]))
ff('-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', os.path.join(OUT, 'banco_pinza_comparacion.mp4'))
print('listo', flush=True)
