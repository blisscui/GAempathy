"""Final figures: Fig 2 (empathy: reference frames + all person-level tests), Fig 3 (exploratory Contempt consensus)."""
import os, sys, json, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.collections import PolyCollection
HERE = os.path.dirname(os.path.abspath(__file__)); FIN = os.environ.get('GA_OUT', os.path.join(HERE, 'final')); OUT = os.path.join(FIN, 'figs')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _style import apply_style, COLORS
apply_style(); plt.rcParams.update({'axes.titlesize': 9, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left'})
R = json.load(open(os.path.join(FIN, 'results.json'))); F = np.load(os.path.join(FIN, 'fig_person_level.npz'))
E = sorted(['Amusement','Anger','Awe','Contempt','Disgust','Embarrassment','Fear','Happiness','Interest','Pride','Sadness','Shame','Surprise'])
N = 53
def ci95(r): z = np.arctanh(r); s = 1/np.sqrt(N-3); return np.tanh(z-1.96*s), np.tanh(z+1.96*s)
def save(fig, name): fig.savefig(os.path.join(OUT, name), dpi=300, bbox_inches='tight'); plt.close(fig); print('wrote', name)
which = sys.argv[1:] or ['2', '3']

if '2' in which:
    fig = plt.figure(figsize=(7.2, 7.4))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 0.82], width_ratios=[1, 1, 0.05], hspace=0.28, wspace=0.12, left=0.17, right=0.92, top=0.95, bottom=0.07)
    D0 = np.loadtxt(os.path.join(FIN, 'fig3_d_original.csv'), delimiter=','); DG = np.loadtxt(os.path.join(FIN, 'fig3_d_common.csv'), delimiter=',')
    iA, iC = E.index('Amusement'), E.index('Contempt')
    for j, (D, ttl) in enumerate([(D0, 'a  Group-specific reference'), (DG, 'b  Common reference')]):
        D = D.copy(); np.fill_diagonal(D, np.nan); ax = fig.add_subplot(gs[0, j])
        im = ax.imshow(D, cmap='RdBu', vmin=-1.4, vmax=1.4)
        ax.add_patch(Rectangle((iC-.5, iA-.5), 1, 1, fill=False, ec='black', lw=1.5))
        ax.set_xticks(range(13)); ax.set_xticklabels([e[:4] for e in E], rotation=90, fontsize=6.5)
        ax.set_yticks(range(13)); ax.set_yticklabels(E if j == 0 else [], fontsize=6.5)
        ax.set_title(ttl); ax.spines[:].set_visible(False); ax.tick_params(length=0)
        ax.set_xlabel('Reference affect', fontsize=7.5)
        if j == 0: ax.set_ylabel("Participant's own prototype", fontsize=7.5)
    cax = fig.add_subplot(gs[0, 2]); cb = fig.colorbar(im, cax=cax)
    cb.set_label("Cohen's d, higher − lower EQ\n(negative = higher EQ closer)", fontsize=6.5); cb.ax.tick_params(labelsize=6)
    RF = R['reference_frames_AxC']
    rows = [('Amusement × Contempt', None),
            ('  group-specific reference', (RF['group_incl|cosine']['r_EQ'], RF['group_incl|cosine']['BF01_r'])),
            ('  group-specific, excluding self', (RF['group_loo|cosine']['r_EQ'], RF['group_loo|cosine']['BF01_r'])),
            ('  common reference', (RF['global_loo|cosine']['r_EQ'], RF['global_loo|cosine']['BF01_r'])),
            ('  own Amusement vs own Contempt', (RF['within|cosine']['r_EQ'], RF['within|cosine']['BF01_r'])),
            ('Person-level tests', None),
            ('  typicality', (R['typicality']['r'], R['typicality']['BF01'])),
            ('  granularity', (R['granularity']['r'], R['granularity']['BF01'])),
            ('  geometry conventionality', (R['geometry_conventionality']['r'], R['geometry_conventionality']['BF01'])),
            ('  identifiability', (R['decoding_accuracy']['r'], R['decoding_accuracy']['BF01'])),
            ('  prototype reliability', (R['reliability_EQ']['r'], R['reliability_EQ']['BF01']))]
    ax = fig.add_subplot(gs[1, :2]); ax.set_title('c  Correlation with Empathy Quotient (n = 53)', x=-0.28)
    for y, (lab, v) in enumerate(rows):
        if v is None:
            ax.text(-0.02, y, lab.strip(), fontsize=7.5, fontweight='bold', va='center', ha='right', transform=ax.get_yaxis_transform()); continue
        r, bf = v; lo, hi_ = ci95(r); orig = 'group-specific' in lab
        c = COLORS['low_empathy'] if orig else COLORS['accent']
        ax.plot([lo, hi_], [y, y], color=c, lw=1.4); ax.plot(r, y, 'o', color=c, ms=5)
        ax.text(-0.02, y, lab.strip(), fontsize=7.5, va='center', ha='right', transform=ax.get_yaxis_transform())
        ax.text(1.02, y, f'{r:+.2f}   {bf:4.1f}', fontsize=7.5, va='center', ha='left', family='DejaVu Sans Mono', transform=ax.get_yaxis_transform())
    ax.text(1.02, -1.1, '  r      BF$_{01}$', fontsize=7.5, ha='left', va='center', fontweight='bold', transform=ax.get_yaxis_transform())
    ax.axvline(0, color='#333', lw=0.8); ax.set_xlim(-0.75, 0.75); ax.set_ylim(len(rows) - 0.5, -1.6)
    ax.set_xticks([-0.5, 0, 0.5]); ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xlabel('Pearson r with 95% CI'); ax.axvspan(-0.25, 0.25, ymin=0, ymax=0, alpha=0)
    save(fig, 'Fig2_empathy.png')

if '3' in which:
    import render_faces as rf
    P = np.load(os.path.join(FIN, 'consensus_prototypes.npy'))
    k = float(os.environ.get('CARICATURE', 2.5))
    fig = plt.figure(figsize=(7.6, 3.9))
    gs = fig.add_gridspec(2, 4, width_ratios=[1.25, 1, 1, 1.75], wspace=0.06, hspace=0.22, left=0.12, right=0.99, top=0.87, bottom=0.13)
    a = fig.add_subplot(gs[:, 0]); C = R['consensus_per_affect']; o = np.argsort([-c['dist'] for c in C])
    for y, i in enumerate(o):
        c = C[i]; col = COLORS['low_empathy'] if c['p_fwer'] < .05 else '#9aa7b8'
        a.barh(y, c['dist'], color=col, height=0.62)
        a.plot([F['cons_null'][i], F['cons_null95'][i]], [y, y], color='#222', lw=0.9); a.plot(F['cons_null'][i], y, '|', color='#222', ms=5)
    a.set_yticks(range(13)); a.set_yticklabels([C[i]['affect'] for i in o], fontsize=7); a.invert_yaxis()
    a.set_xlabel('Cosine distance, higher-\nvs lower-EQ consensus', fontsize=7.5); a.set_xticks([0, 0.5, 1.0])
    fig.text(0.01, 0.95, 'a  Group consensus', fontsize=9, fontweight='bold')
    for r_, g, glab in [(0, 0, 'Higher EQ'), (1, 1, 'Lower EQ')]:
        for c_, aff in [(1, 'Amusement'), (2, 'Contempt')]:
            ax = fig.add_subplot(gs[r_, c_]); rf.draw(ax, k * P[g, E.index(aff)])
            ax.set_title(f'{glab}, {aff.lower()}', fontsize=7.5, fontweight='normal', loc='center')
    fig.text(0.33, 0.95, f'b  Consensus prototypes (shape ×{k:g})', fontsize=9, fontweight='bold')
    fig.text(0.70, 0.95, 'c  Contempt: higher − lower EQ', fontsize=9, fontweight='bold')
    ax = fig.add_subplot(gs[:, 3]); V0 = rf.mesh(np.zeros(199))
    dV = rf.mesh(k*P[0, E.index('Contempt')]) - rf.mesh(k*P[1, E.index('Contempt')])
    T = V0[rf.TL]; n = -np.cross(T[:, 1]-T[:, 0], T[:, 2]-T[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True)
    disp = np.einsum('tj,tj->t', dV[rf.TL].mean(1), n) / 1000.0
    vis = n[:, 2] > 0; od = np.argsort(T[vis, :, 2].mean(1)); lim = np.percentile(np.abs(disp[vis]), 98)
    cm = plt.get_cmap('RdBu_r'); cols = cm(0.5 + 0.5*np.clip(disp[vis][od]/lim, -1, 1))
    ax.add_collection(PolyCollection(T[vis][od][:, :, :2], facecolors=cols, edgecolors='none', antialiased=False))
    ax.set_xlim(V0[:, 0].min(), V0[:, 0].max()); ax.set_ylim(V0[:, 1].min(), V0[:, 1].max()); ax.set_aspect('equal'); ax.axis('off')
    ax.set_anchor('N')
    sm = plt.cm.ScalarMappable(cmap=cm, norm=plt.Normalize(-lim, lim))
    cb = fig.colorbar(sm, ax=ax, orientation='horizontal', fraction=0.045, pad=0.02, aspect=18)
    cb.set_label('Outward displacement (mm)', fontsize=7); cb.ax.tick_params(labelsize=6)
    save(fig, 'Fig3_contempt_consensus.png')
