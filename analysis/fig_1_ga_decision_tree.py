"""Figure 1 — GA next-generation breeding rule.

Flowchart showing the deterministic rule that turns the faces selected
in generation N into the 12 faces displayed in generation N+1.

Root:    Generation N  (s faces selected)
Branches: s = 0     -> 12 random faces
         s = 1     -> 6 crossed + 6 random
         s = 2     -> 6 crossover + 6 random
         s >= 3    -> 6 crossover (random parent pairs) + 6 random

Output: manuscript_figures/out/fig_1_ga_decision_tree.png
"""

import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from _style import apply_style, COLORS, save_fig


def box(ax, x, y, w, h, text, fontsize=10, fontweight='normal',
        facecolor='white', edgecolor=None, textcolor='#111', italic=False):
    edgecolor = edgecolor or COLORS['accent']
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle='round,pad=0.02,rounding_size=0.12',
        facecolor=facecolor, edgecolor=edgecolor, linewidth=1.3
    )
    ax.add_patch(patch)
    style = 'italic' if italic else 'normal'
    ax.text(x + w / 2, y + h / 2, text,
            ha='center', va='center',
            fontsize=fontsize, fontweight=fontweight,
            color=textcolor, style=style,
            linespacing=1.3)


def arrow(ax, x1, y1, x2, y2, color='#555'):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle='-|>,head_width=4,head_length=6',
        mutation_scale=1.0, linewidth=1.4, color=color
    )
    ax.add_patch(a)


def build():
    apply_style()
    fig, ax = plt.subplots(figsize=(14, 7.0))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8.5)
    ax.axis('off')

    # Root node
    root_x, root_y, root_w, root_h = 5.0, 6.8, 4.0, 0.85
    box(ax, root_x, root_y, root_w, root_h,
        'Generation N\ns faces selected',
        fontsize=12, fontweight='bold',
        facecolor=COLORS['bg'], edgecolor=COLORS['accent'])

    # Branch condition labels + child nodes
    branches = [
        {
            's_text': 's = 0',
            'x_center': 1.7,
            'headline': '12 new\nrandom faces',
            'detail':  'No parents; next\ngeneration is random.',
            'color':   COLORS['neutral'],
        },
        {
            's_text': 's = 1',
            'x_center': 5.0,
            'headline': '6 crossed\n(50% parent + 50% novel)\n+ 6 random',
            'detail':  'Single parent crossed\nwith novel faces.',
            'color':   COLORS['accent'],
        },
        {
            's_text': 's = 2',
            'x_center': 8.5,
            'headline': '6 crossover\n(50% parent A + 50% B)\n+ 6 random',
            'detail':  'Pairwise crossover of\nthe 2 selected parents.',
            'color':   COLORS['accent'],
        },
        {
            's_text': u's \u2265 3',
            'x_center': 12.0,
            'headline': '6 crossover\n(2 random parents from s)\n+ 6 random',
            'detail':  'Each offspring from 2\nparents drawn at random.',
            'color':   COLORS['accent'],
        },
    ]

    child_w, child_h = 3.0, 1.25
    detail_w, detail_h = 3.0, 0.80
    s_label_w, s_label_h = 1.2, 0.42

    root_cx = root_x + root_w / 2

    for br in branches:
        cx = br['x_center']

        # s = ... label
        box(ax, cx - s_label_w / 2, 5.7, s_label_w, s_label_h,
            br['s_text'], fontsize=10, fontweight='bold',
            facecolor='white', edgecolor=br['color'], textcolor=br['color'])

        # Arrow: root -> s-label
        arrow(ax, root_cx, root_y - 0.02, cx, 6.14,
              color=br['color'])

        # Offspring-rule box
        box(ax, cx - child_w / 2, 3.9, child_w, child_h,
            br['headline'], fontsize=9.5, fontweight='bold',
            facecolor=COLORS['bg'], edgecolor=br['color'])

        # Arrow: s-label -> offspring box
        arrow(ax, cx, 5.68, cx, 5.17, color=br['color'])

        # Detail box
        box(ax, cx - detail_w / 2, 2.65, detail_w, detail_h,
            br['detail'], fontsize=8.5, italic=True,
            facecolor='white', edgecolor='#bbb', textcolor='#555')

        # Connector
        arrow(ax, cx, 3.88, cx, 3.47, color='#999')

    # Footer
    footer_y = 0.85
    box(ax, 0.3, 0.2, 13.4, 1.9, '', facecolor='#fbfbfb', edgecolor=COLORS['accent'])
    ax.text(7, footer_y + 0.85,
            'Every non-empty generation includes 6 novel faces to prevent premature convergence.',
            fontsize=10, color='#222', ha='center', fontweight='bold')
    ax.text(7, footer_y + 0.35,
            u'Crossover: each offspring inherits 50% of one parent\u2019s 199 shape coefficients',
            fontsize=9.5, color='#444', ha='center')
    ax.text(7, footer_y + 0.0,
            'and 50% from the other (or from a novel face), drawn independently per dimension.',
            fontsize=9.5, color='#444', ha='center')
    ax.text(7, footer_y - 0.45,
            '7 generations per affect; 13 affects per participant, randomized order.',
            fontsize=9.5, color='#444', ha='center', style='italic')

    fig.tight_layout()
    save_fig(fig, 'fig_1_ga_decision_tree')


if __name__ == '__main__':
    build()
