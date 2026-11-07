"""Render consensus face prototypes from Basel Face Model 2009 shape coefficients (SD units), shape only, mean texture-free grey shading.
Matches GAfaceSpace coef2object: vertices = shapeMU + shapePC @ (coef * shapeEV)."""
import os, sys, numpy as np, scipy.io as sio, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
BFM = os.environ.get('BFM_MAT', '01_MorphableModel.mat')   # Basel Face Model 2009; obtain from https://faces.dmi.unibas.ch/bfm/
m = sio.loadmat(BFM, variable_names=['shapeMU', 'shapePC', 'shapeEV', 'tl', 'texMU'])
MU, PC, EV, TL = m['shapeMU'][:, 0].astype(float), m['shapePC'].astype(float), m['shapeEV'][:, 0].astype(float), m['tl'].astype(int) - 1
TEX = np.clip(m['texMU'][:, 0].astype(float).reshape(-1, 3) / 255.0, 0, 1)   # mean albedo (texture was not varied in the task)
def mesh(coef): return (MU + PC @ (coef * EV)).reshape(-1, 3)
def draw(ax, coef, title=None, texture=True):
    V = mesh(coef); T = V[TL]                                   # triangles x 3 x 3
    n = -np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    L = np.array([0.3, 0.4, 1.0]); L /= np.linalg.norm(L)
    shade = 0.35 + 0.65 * np.clip(n @ L, 0, 1)
    vis = n[:, 2] > 0; order = np.argsort(T[vis, :, 2].mean(1))
    polys = T[vis][order][:, :, :2]; base = TEX[TL].mean(1) if texture else np.full((len(TL), 3), 0.85)
    cols = np.clip(base[vis][order] * shade[vis][order][:, None], 0, 1)
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors='none', antialiased=False))
    ax.set_xlim(V[:, 0].min(), V[:, 0].max()); ax.set_ylim(V[:, 1].min(), V[:, 1].max())
    ax.set_aspect('equal'); ax.axis('off')
    if title: ax.set_title(title, fontsize=9)
if __name__ == '__main__':
    P = np.load(os.path.join(os.environ.get('GA_OUT', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'final')), 'consensus_prototypes.npy'))  # hi, lo, all
    E = sorted(['Embarrassment','Awe','Sadness','Fear','Happiness','Disgust','Amusement','Anger','Contempt','Surprise','Interest','Pride','Shame'])
    scale = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    fig, axs = plt.subplots(2, 3, figsize=(7, 5.2))
    for r, (gi, gname) in enumerate([(0, 'Higher EQ'), (1, 'Lower EQ')]):
        for c, (aff) in enumerate(['Amusement', 'Contempt', 'Happiness']):
            draw(axs[r, c], scale * P[gi, E.index(aff)], f'{gname}: {aff}')
    plt.tight_layout(); out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'final', f'render_test_x{scale:g}.png')
    plt.savefig(out, dpi=110); print(out, 'max |coef|', np.abs(P).max())
