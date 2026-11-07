# Self-generated facial affect prototypes are reliable but largely independent of trait empathy

Code for Cui & Bex (manuscript under review).

## Contents

| Folder | What it is |
| --- | --- |
| `task/` | MATLAB / Psychtoolbox-3 genetic-algorithm face task (`run_experiment.m`, `src/matlab/+facespace`, `config/`) |
| `analysis/revision_analysis.py` | Single script that computes every statistic reported in the paper and writes `final/results.json` |
| `analysis/make_figs_v2.py` | Figures 2 and 3 (reads `final/`) |
| `analysis/render_faces.py` | Renders Basel Face Model prototypes (used by Figure 3) |
| `analysis/fig_1_ga_decision_tree.py` | Figure 1 schematic |
| `analysis/loaders.py` | Data loaders: EQ scoring and per-participant prototypes (median of all selected faces) |

## Data

Participant data (face-task selections, Empathy Quotient, demographics, BDI-II totals) are available from the
corresponding author (cui.bl@northeastern.edu) on reasonable request. Place them in one folder:

```
data/
  GASstatsData/                     one folder per participant (trial records + raw_arrays/shapeVals_*.csv)
  Empathy Quotient Questionnaire (BC 2024) (Responses).csv
  Demographic Mental Health + Ocular Health Questionnaire (BC 2024) (Responses) (1).xlsx
  bdi_totals.csv                    columns: subject_id, bdi_total
```

The Basel Face Model 2009 (`01_MorphableModel.mat`) is licensed separately and must be obtained from
https://faces.dmi.unibas.ch/bfm/. It is needed only for the task and for rendering faces.

## Running

```
pip install -r requirements.txt
export GA_DATA_ROOT=/path/to/data          # default: ../data
export GA_OUT=/path/to/output              # default: analysis/final
export BFM_MAT=/path/to/01_MorphableModel.mat
python analysis/revision_analysis.py       # ~70 s with 5,000 permutations (set NPERM=200 for a quick test)
python analysis/make_figs_v2.py 2 3
```

Permutation and bootstrap analyses use 5,000 iterations and random seed 42.

## Citation

Cui, B. H. & Bex, P. J. Self-generated facial affect prototypes are reliable but largely independent of trait
empathy. Manuscript under review. Code archived on Zenodo: https://doi.org/10.5281/zenodo.24025733

Supported by NEI award R01EY032162.
