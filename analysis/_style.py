"""Shared plotting style for manuscript figures.

Import at the top of every figure script:

    from _style import apply_style, EMOTIONS, COLORS, save_fig
"""

import os
import matplotlib as mpl
import matplotlib.pyplot as plt


EMOTIONS = [
    'Amusement', 'Anger', 'Awe', 'Contempt', 'Disgust', 'Embarrassment',
    'Fear', 'Happiness', 'Interest', 'Pride', 'Sadness', 'Shame', 'Surprise'
]

# Brand-ish palette: high-empathy teal, low-empathy warm rust.
COLORS = {
    'high_empathy': '#1f7a8c',   # teal
    'low_empathy':  '#c85250',   # warm rust
    'neutral':      '#4a4a4a',   # dark grey
    'accent':       '#1f3864',   # deep navy (titles, highlights)
    'muted':        '#808080',
    'pos_diff':     '#1f7a8c',   # high > low
    'neg_diff':     '#c85250',   # high < low
    'bg':           '#f7f7f7',
}


def apply_style():
    """Apply a consistent matplotlib rc style for all figures."""
    mpl.rcParams.update({
        'figure.dpi': 100,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 10,
        'axes.titlesize': 12,
        'axes.titleweight': 'bold',
        'axes.labelsize': 10,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.edgecolor': '#333333',
        'axes.linewidth': 0.8,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'xtick.color': '#333333',
        'ytick.color': '#333333',
        'legend.fontsize': 9,
        'legend.frameon': False,
        'grid.color': '#dddddd',
        'grid.linewidth': 0.5,
    })


def save_fig(fig, stem, out_dir=None):
    """Save figure as a PNG (high-DPI)."""
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(__file__), 'out')
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, f'{stem}.png')
    fig.savefig(png_path)
    print(f'  Wrote {png_path}')
    plt.close(fig)
