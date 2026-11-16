# Figura: giro de muñeca y error lateral en el cierre por posición del cubo pedido (izquierda/centro/derecha).
# Uso: python figura_derecha.py <intentos_por_posicion.csv> <salida_sin_extension>
import sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

F = pd.read_csv(sys.argv[1]); F = F[F.n_intento == 1]
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.edgecolor': '#1A1A1A', 'axes.labelcolor': '#1A1A1A', 'xtick.color': '#1A1A1A', 'ytick.color': '#1A1A1A',
                     'svg.fonttype': 'none', 'pdf.fonttype': 42})
COL = {'40k': '#CA8A04', 'pinza=orden': '#1A1A1A', 'ACT': '#9CA3AF', 'v2': '#1D4ED8'}
NOM = {'40k': 'SmolVLA 40k', 'pinza=orden': 'SmolVLA pinza = orden', 'ACT': 'ACT', 'v2': 'SmolVLA v2'}
POS = ['izquierda', 'centro', 'derecha']
rng = np.random.default_rng(0)


def panel(ax, X, pols, col, esc, titulo, ylab, ylim=None, ref=None):
    w = 0.8 / len(pols)
    for i, pos in enumerate(POS):
        for j, pol in enumerate(pols):
            d = X[(X.politica == pol) & (X.posicion == pos)]
            if not len(d): continue
            v = esc * d[col].values; x0 = i - 0.4 + w * (j + 0.5)
            xs = x0 + rng.uniform(-w * 0.28, w * 0.28, len(v))
            ok = d.exito.values == 1
            vv = np.clip(v, *ylim) if ylim else v
            ax.scatter(xs[ok], vv[ok], s=11, color=COL[pol], lw=0, zorder=3)
            ax.scatter(xs[~ok], vv[~ok], s=11, facecolor='white', edgecolor=COL[pol], lw=0.8, zorder=3)
            m = np.median(v)
            ax.plot([x0 - w * 0.38, x0 + w * 0.38], [np.clip(m, *ylim) if ylim else m] * 2, color=COL[pol], lw=1.6, zorder=4)
            y0 = ylim[0] + (ylim[1] - ylim[0]) * (0.01 if j % 2 == 0 else 0.065)
            ax.text(x0, y0, f'{ok.sum()}/{len(ok)}', ha='center', va='bottom', fontsize=5.5, color=COL[pol] if pol != 'ACT' else '#6B7280')
    if ref is not None:
        ax.axhline(ref, color='#9CA3AF', lw=0.6, ls='--', zorder=1)
    ax.set_xticks(range(3)); ax.set_xticklabels(['Izquierda', 'Centro', 'Derecha'])
    ax.set_xlim(-0.5, 2.5); ax.set_ylabel(ylab); ax.set_title(titulo, fontsize=8.5, loc='left', color='#1A1A1A')
    if ylim: ax.set_ylim(*ylim)


fig, axs = plt.subplots(1, 3, figsize=(7.2, 3.0), constrained_layout=True)
M = F[F.fuente == 'mision']; B = F[F.fuente == 'banco_s910']
panel(axs[0], M, ['40k', 'pinza=orden', 'v2'], 'droll', 1, '(a) Misión: giro de muñeca', 'Giro de muñeca (°)', (-40, 40), 0)
panel(axs[1], B, ['40k', 'ACT', 'v2'], 'err_giro', 1, '(b) s910: giro − giro del experto', 'Error de giro (°)', (-55, 35), 0)
panel(axs[2], B, ['40k', 'ACT', 'v2'], 'err_u_nominal', 1000, '(c) s910: error lateral', 'Error lateral +u (mm)', (-25, 32), 0)
axs[2].axhspan(3, 32, color='#CA8A04', alpha=0.07, lw=0, zorder=0)
axs[2].text(-0.45, 31, 'hacia la mordaza fija', ha='left', va='top', fontsize=6.5, color='#1A1A1A')
axs[2].text(2.47, -7, 'hacia la holgura' + chr(10) + '(mordaza móvil)', ha='right', va='top', fontsize=6.5, color='#1A1A1A')
from matplotlib.lines import Line2D
h = [Line2D([], [], marker='o', ls='', color=COL[p], label=NOM[p], ms=4) for p in ['40k', 'pinza=orden', 'ACT', 'v2']]
h += [Line2D([], [], marker='o', ls='', color='#6B7280', label='éxito', ms=4),
      Line2D([], [], marker='o', ls='', markerfacecolor='white', markeredgecolor='#6B7280', label='fallo', ms=4)]
fig.legend(handles=h, loc='outside lower center', ncol=6, frameon=False, fontsize=7)
for ext in ('svg', 'pdf', 'png'):
    fig.savefig(sys.argv[2] + '.' + ext, dpi=200)
