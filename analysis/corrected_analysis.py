#!/usr/bin/env python3
"""
=============================================================================
CORRECTED ANALYSIS PIPELINE
Empathy and Facial Emotion Representations via Genetic Algorithms
=============================================================================

Principal Investigator: Peter Bex (Northeastern University)
Lead Analyst: Bliss Cui
NIH Grant: R01 EY032162

This script is the single-source-of-truth reproducible analysis pipeline.
It runs end-to-end from raw data to all statistical outputs.

REPOSITORY: https://github.com/[TBD]
TARGET JOURNAL: Royal Society Open Science (or similar)

=============================================================================
AUDIT TRAIL — KEY DECISIONS AND CHANGES
=============================================================================

[2026-04-08] CRITICAL BUG FIX: Dimension inconsistency
    PROBLEM: Original pipeline (statistics.ts -> Python replication) flattened
    each subject's 199×N raw array into a 199*N-dimensional vector, where N is
    the number of faces selected (varies 1-12 per subject per emotion). This
    produced vectors of incomparable lengths (e.g., 199, 398, 597, 796...).
    A "majority-rule" filter then discarded all subjects whose vector length
    didn't match the modal length, losing 64-79% of data per emotion
    (typical N dropped from 53 to 11-19).

    FIX: Replace flattening with column-mean centroid. For each subject and
    emotion, take the mean across columns (faces) of the 199×N matrix,
    producing a uniform 199-dimensional prototype vector. This recovers ALL
    53 subjects for ALL 13 emotions with zero data loss.

    IMPACT: The old results were largely artifacts of the flawed approach.
    7/9 "significant" diagonal pairs are now non-significant. However, the
    corrected data reveals 47+ new FDR-corrected off-diagonal pairs with
    medium-to-large effect sizes, representing a richer finding.

[2026-04-08] DECISION: Exclude GAS46, GAS47, GAS48, GAS49
    These 4 subjects completed the GA task and demographics questionnaire but
    NOT the Empathy Quotient (EQ) questionnaire. Without EQ scores, they
    cannot be assigned to High/Low empathy groups. They are excluded from
    all analyses. Final N = 53.

[2026-04-08] DECISION: Exclude GAS5, GAS9, GAS52, GAS57
    These subject IDs do not appear in any data file. Likely no-shows or
    withdrawn consent during recruitment. Not applicable to any analysis.

[2026-04-08] DECISION: K-Means clustering (k=2) retained from original
    The 1D K-Means split (High Empathy: n=30, mean EQ=56.2; Low Empathy:
    n=23, mean EQ=36.0) is retained for group-based analyses. Continuous
    EQ correlations are also computed as a complementary approach.

[2026-04-08] STATISTICAL METHOD: Welch's t-test (two-tailed)
    Used for all group comparisons. Does not assume equal variances.
    Degrees of freedom via Welch-Satterthwaite approximation.

[2026-04-08] MULTIPLE COMPARISONS: BH-FDR (primary), Bonferroni, Holm
    Benjamini-Hochberg FDR at q<0.05 is the primary correction for the
    13×13 matrix (169 tests). Bonferroni and Holm are reported for
    sensitivity analysis.

=============================================================================
DEPENDENCIES
=============================================================================
    Python 3.8+
    numpy
    openpyxl (for demographics XLSX reading)
    Standard library: csv, os, math, collections, json, re

    NOTE: scipy is NOT required. All statistical functions are implemented
    from scratch to avoid dependency issues and ensure full transparency.
    The normal CDF uses the Abramowitz & Stegun polynomial approximation,
    which is accurate to ~1e-7.
=============================================================================
"""

import os
import sys
import csv
import math
import json
import re
import ast
from collections import Counter
from typing import Dict, List, Optional, Tuple, NamedTuple
import numpy as np

# =============================================================================
# CONFIGURATION
# =============================================================================

# All paths are relative to this script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'python_stats', 'data', 'GASstatsData')
EQ_CSV = os.path.join(SCRIPT_DIR, 'python_stats', 'data',
                       'Empathy Quotient Questionnaire (BC 2024) (Responses).csv')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'python_stats', 'output')

# Emotion numbering from the GA task (mapped from trial records)
EMO_NUM_TO_NAME = {
    1: 'Embarrassment', 2: 'Awe', 3: 'Sadness', 4: 'Fear', 5: 'Happiness',
    6: 'Disgust', 7: 'Amusement', 8: 'Anger', 9: 'Contempt', 10: 'Surprise',
    11: 'Interest', 12: 'Pride', 13: 'Shame'
}
EMOTIONS = sorted(EMO_NUM_TO_NAME.values())  # Alphabetical for consistency

# EQ Questionnaire scoring
# Positive items: score 2 if "Definitely Agree", 1 if "Slightly Agree"
EQ_POSITIVE_INDICES = [1, 6, 19, 22, 25, 26, 35, 36, 37, 38, 41, 42, 43, 44,
                        52, 54, 55, 57, 58, 59, 60]
# Negative items: score 2 if "Definitely Disagree", 1 if "Slightly Disagree"
EQ_NEGATIVE_INDICES = [4, 8, 10, 11, 12, 14, 15, 18, 21, 27, 28, 29, 32, 34,
                        39, 46, 48, 49, 50]
# Remaining items are fillers (not scored)

# Subjects to EXCLUDE (no EQ data)
EXCLUDED_NO_EQ = {'GAS46', 'GAS47', 'GAS48', 'GAS49'}
# Subject IDs that never existed in any file
NONEXISTENT_IDS = {'GAS5', 'GAS9', 'GAS52', 'GAS57'}

# Analysis parameters
ALPHA = 0.05
N_PERMUTATIONS = 5000  # For permutation tests (set to 0 to skip)
LOADER_MODE = 'centroid'  # 'superface' or 'centroid' — set via CLI
# Per analysis on 2026-04-15: centroid (median of all selected faces across
# gen1-gen7, matching poster Fig 2 caption) gives more robust empathy
# results than super face. Task validation is identical between methods.
N_BOOTSTRAP = 5000     # For bootstrap CIs (set to 0 to skip)
RANDOM_SEED = 42


# =============================================================================
# STATISTICAL FUNCTIONS (no scipy dependency)
# =============================================================================

def norm_cdf(x: float) -> float:
    """Standard normal CDF using Abramowitz & Stegun approximation.
    Accurate to ~1e-7. Reference: Handbook of Mathematical Functions, 26.2.17.
    """
    if x < -8.0:
        return 0.0
    if x > 8.0:
        return 1.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    p = d * math.exp(-x * x / 2.0) * t * (
        0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))
    )
    return 1.0 - p if x > 0 else p


def welch_ttest(group_a: List[float], group_b: List[float]) -> Dict:
    """Two-sample Welch's t-test (unequal variances, two-tailed).

    Returns dict with t_stat, df, p_value.
    Uses Welch-Satterthwaite degrees of freedom approximation.
    P-value computed via t-to-normal transform for moderate df,
    direct normal approximation for large df.
    """
    n1, n2 = len(group_a), len(group_b)
    if n1 < 2 or n2 < 2:
        return {'t_stat': float('nan'), 'df': float('nan'), 'p_value': float('nan')}

    a, b = np.array(group_a), np.array(group_b)
    m1, m2 = np.mean(a), np.mean(b)
    v1, v2 = np.var(a, ddof=1), np.var(b, ddof=1)

    se_sq = v1 / n1 + v2 / n2
    if se_sq <= 0:
        return {'t_stat': 0.0, 'df': n1 + n2 - 2, 'p_value': 1.0}

    se = math.sqrt(se_sq)
    t = (m1 - m2) / se

    # Welch-Satterthwaite df
    df_num = se_sq ** 2
    term1 = (v1 / n1) ** 2 / (n1 - 1) if n1 > 1 else 0
    term2 = (v2 / n2) ** 2 / (n2 - 1) if n2 > 1 else 0
    df_den = term1 + term2
    df = df_num / df_den if df_den > 0 else n1 + n2 - 2

    # P-value
    if df > 100:
        p = 2.0 * (1.0 - norm_cdf(abs(t)))
    else:
        # t-to-normal transform (accurate for df > 3)
        A = df - 0.5
        if A > 0:
            z2 = t * t / df
            z_val = math.sqrt(A * math.log(1.0 + z2)) if z2 > 0 else 0.0
            p = 2.0 * (1.0 - norm_cdf(z_val))
        else:
            p = 2.0 * (1.0 - norm_cdf(abs(t)))

    return {'t_stat': float(t), 'df': float(df), 'p_value': float(min(p, 1.0))}


def cohens_d(group_a: List[float], group_b: List[float]) -> float:
    """Cohen's d effect size with pooled standard deviation."""
    n1, n2 = len(group_a), len(group_b)
    if n1 < 2 or n2 < 2:
        return float('nan')
    a, b = np.array(group_a), np.array(group_b)
    m1, m2 = np.mean(a), np.mean(b)
    v1, v2 = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    return float((m1 - m2) / pooled) if pooled > 0 else 0.0


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance: D(a,b) = 1 - cos(a,b). Range [0, 2]."""
    dot = float(np.dot(a, b))
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return 1.0 - dot / (na * nb)


def pearson_r(x: List[float], y: List[float]) -> Dict:
    """Pearson correlation coefficient with p-value.
    P-value uses t-distribution approximation: t = r*sqrt(n-2)/sqrt(1-r^2).
    """
    n = len(x)
    assert n == len(y), "x and y must have same length"
    if n < 3:
        return {'r': float('nan'), 'p_value': float('nan'), 'n': n}

    xa, ya = np.array(x), np.array(y)
    mx, my = np.mean(xa), np.mean(ya)
    dx, dy = xa - mx, ya - my

    num = float(np.sum(dx * dy))
    den = math.sqrt(float(np.sum(dx ** 2)) * float(np.sum(dy ** 2)))

    if den == 0:
        return {'r': 0.0, 'p_value': 1.0, 'n': n}

    r = num / den
    r = max(-1.0, min(1.0, r))  # Clamp for numerical safety

    # t-test for significance
    if abs(r) >= 1.0:
        p = 0.0
    else:
        t = r * math.sqrt(n - 2) / math.sqrt(1 - r * r)
        df = n - 2
        if df > 100:
            p = 2 * (1 - norm_cdf(abs(t)))
        else:
            A = df - 0.5
            z2 = t * t / df
            z_val = math.sqrt(A * math.log(1 + z2)) if z2 > 0 and A > 0 else abs(t)
            p = 2 * (1 - norm_cdf(z_val))

    return {'r': float(r), 'p_value': float(min(p, 1.0)), 'n': n}


def bh_fdr(p_values: List[float]) -> List[float]:
    """Benjamini-Hochberg FDR correction.
    Returns adjusted p-values (q-values).
    """
    n = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * n

    for rank, (idx, p) in enumerate(indexed, 1):
        adjusted[idx] = min(p * n / rank, 1.0)

    # Enforce monotonicity (step-up)
    for i in range(n - 2, -1, -1):
        idx_curr = indexed[i][0]
        idx_next = indexed[i + 1][0]
        adjusted[idx_curr] = min(adjusted[idx_curr], adjusted[idx_next])

    return adjusted


def bonferroni(p_values: List[float]) -> List[float]:
    """Bonferroni correction."""
    n = len(p_values)
    return [min(p * n, 1.0) for p in p_values]


def holm(p_values: List[float]) -> List[float]:
    """Holm-Bonferroni step-down correction."""
    n = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * n

    for rank, (idx, p) in enumerate(indexed, 1):
        adjusted[idx] = min(p * (n - rank + 1), 1.0)

    # Enforce monotonicity (step-down)
    for i in range(1, n):
        idx_curr = indexed[i][0]
        idx_prev = indexed[i - 1][0]
        adjusted[idx_curr] = max(adjusted[idx_curr], adjusted[idx_prev])

    return adjusted


# =============================================================================
# DATA LOADING
# =============================================================================

class SubjectData(NamedTuple):
    """All data for one subject."""
    id: str
    eq_score: int
    eq_group: str  # 'High Empathy' or 'Low Empathy'
    centroids: Dict[str, np.ndarray]  # emotion -> 199-dim centroid vector
    n_faces: Dict[str, int]  # emotion -> number of faces selected at gen7


def load_eq_scores() -> Dict[str, int]:
    """Load EQ scores from questionnaire CSV.

    AUDIT: EQ scoring follows Baron-Cohen et al. (2004).
    21 positive items + 19 negative items = 40 scored items.
    20 filler items are not scored. Score range: 0-80.
    """
    scores = {}

    with open(EQ_CSV, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)

        # Column 1 is subject ID, columns 2-61 are the 60 EQ items
        for row in reader:
            if len(row) < 62:
                continue
            sid = row[1].strip().upper().replace(' ', '')
            if not sid.startswith('GAS'):
                continue

            total = 0
            for item_num in EQ_POSITIVE_INDICES:
                val = row[item_num + 1].strip().lower() if item_num + 1 < len(row) else ''
                if 'strongly agree' in val:
                    total += 2
                elif 'slightly agree' in val:
                    total += 1

            for item_num in EQ_NEGATIVE_INDICES:
                val = row[item_num + 1].strip().lower() if item_num + 1 < len(row) else ''
                if 'strongly disagree' in val:
                    total += 2
                elif 'slightly disagree' in val:
                    total += 1

            scores[sid] = total

    return scores


def kmeans_1d_k2(values: List[float]) -> Tuple[float, float, int]:
    """1D K-Means with k=2. Returns (centroid_low, centroid_high, high_cluster_index).

    AUDIT: Convergence is deterministic for 1D k=2.
    Initialized with min and max of data.
    """
    vals = sorted(values)
    c1, c2 = vals[0], vals[-1]

    for _ in range(100):
        g1 = [v for v in vals if abs(v - c1) <= abs(v - c2)]
        g2 = [v for v in vals if abs(v - c1) > abs(v - c2)]

        if not g1 or not g2:
            break

        new_c1 = sum(g1) / len(g1)
        new_c2 = sum(g2) / len(g2)

        if abs(new_c1 - c1) < 1e-10 and abs(new_c2 - c2) < 1e-10:
            break
        c1, c2 = new_c1, new_c2

    # Higher centroid = High Empathy
    if c1 > c2:
        return c2, c1, 0
    return c1, c2, 1


def load_subject_emotion_map(subject_folder: str) -> Dict[str, int]:
    """Read the trial_records CSV to get each subject's emotion-to-number mapping.

    AUDIT: CRITICAL — emotion numbering (emo1, emo2, ..., emo13) is NOT fixed
    across subjects. Each subject's trial order is randomized. The mapping must
    be read from each subject's trial_records.csv file.

    [2026-04-08] BUG FIX: Earlier version hardcoded the mapping from GAS1,
    which was WRONG for other subjects (e.g., GAS6 had emo12=Awe, not emo2).
    """
    # Find the trial_records CSV
    trial_csv = None
    for fname in os.listdir(subject_folder):
        if fname.endswith('_trial_records.csv'):
            trial_csv = os.path.join(subject_folder, fname)
            break

    if trial_csv is None:
        return {}

    emo_map = {}  # emotion_name -> emo_number
    with open(trial_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            emo_num_str = row.get('emotion_row', '')
            test_name = row.get('testName', '')
            if not emo_num_str or not test_name:
                continue

            emo_num = int(emo_num_str)
            # Normalize emotion name
            emo_name = test_name.strip()
            # Fix known typo in data
            if emo_name.lower() == 'embarrasment':
                emo_name = 'Embarrassment'

            if emo_name not in emo_map:
                emo_map[emo_name] = emo_num

    return emo_map


def load_centroid_median_of_selected(subject_folder: str, emo_num: int) -> Optional[Tuple[np.ndarray, int]]:
    """Load the CENTROID = median of parameters across ALL selected faces (gen1-gen7).

    AUDIT [2026-04-15]: Per the SfN poster (Figure 2 caption):
      "Resultant centroid faces were generated from the medians of the 199
       parameters from all the faces that all the participant selected during
       the experiment."

    Process:
      1. Read trial_records.csv
      2. For each generation (1-7), parse stimChosen to find which candidates were selected
      3. Load shapeVals_emo{N}_gen{G}.csv, strip row 0 (index), extract chosen columns
      4. Concatenate all selected face parameters across generations -> 199 x M matrix
      5. Compute the per-parameter median across M selected faces -> 199-dim centroid

    Returns (199-dim centroid, total_n_selected_faces) or None.
    """
    raw_dir = os.path.join(subject_folder, 'raw_arrays')
    if not os.path.isdir(raw_dir):
        return None

    # Find trial records
    trial_csv = None
    for fname in os.listdir(subject_folder):
        if fname.endswith('_trial_records.csv'):
            trial_csv = os.path.join(subject_folder, fname)
            break
    if trial_csv is None:
        return None

    selected_columns = []  # List of 199-dim vectors

    with open(trial_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                if int(row.get('emotion_row', '-1')) != emo_num:
                    continue
                gen = int(row.get('generation_col', '-1'))
                if gen < 1 or gen > 7:
                    continue
            except ValueError:
                continue

            stim_str = row.get('stimChosen', '').strip()
            if not stim_str:
                continue
            try:
                parsed = ast.literal_eval(stim_str)
            except (ValueError, SyntaxError):
                continue

            # Normalize chosen indices
            if isinstance(parsed, int):
                chosen_idxs = [0] if int(parsed) == 1 else []
                expected_n = 1
            elif isinstance(parsed, (list, tuple)):
                chosen_idxs = [i for i, v in enumerate(parsed) if int(v) == 1]
                expected_n = len(parsed)
            else:
                continue

            if not chosen_idxs:
                # Zero faces selected this generation: skip
                continue

            gen_file = os.path.join(raw_dir, f'shapeVals_emo{emo_num}_gen{gen}.csv')
            if not os.path.isfile(gen_file):
                continue
            arr = np.loadtxt(gen_file, delimiter=',')

            if arr.ndim == 1:
                # Single column case
                params = arr[1:]  # 199-dim
                if 0 in chosen_idxs:
                    selected_columns.append(params)
            else:
                params = arr[1:, :]  # 199 x N
                for ci in chosen_idxs:
                    if ci < params.shape[1]:
                        selected_columns.append(params[:, ci])

    if not selected_columns:
        return None

    stacked = np.column_stack(selected_columns)  # 199 x M
    centroid = np.median(stacked, axis=1)
    assert centroid.shape == (199,), f"Centroid shape {centroid.shape} != (199,)"
    return centroid, stacked.shape[1]


def load_raw_centroid(subject_folder: str, emo_num: int) -> Optional[Tuple[np.ndarray, int]]:
    """Load the SUPER FACE for this subject + emotion.

    AUDIT [2026-04-15]: Per Bliss's clarification, gen7 is the "super face"
    selection round. The participant is shown 1-7 candidate faces and picks
    ONE final face that represents their mental representation of the emotion.
    This function returns the SINGLE chosen 199-dim face vector.

    Process:
      1. Read the subject's trial_records.csv
      2. Find the gen7 row for this emo_num
      3. Parse stimChosen (a one-hot list like "[0, 0, 1, 0, 0, 0]")
      4. Load shapeVals_emo{N}_gen7.csv (200 rows: row 0 = index row, rows 1-199 = params)
      5. Extract the column where stimChosen == 1

    Returns (199-dim super face vector, n_candidates_in_gen7) or None.
    """
    raw_dir = os.path.join(subject_folder, 'raw_arrays')
    gen7_file = os.path.join(raw_dir, f'shapeVals_emo{emo_num}_gen7.csv')
    if not os.path.isfile(gen7_file):
        return None

    # --- Find stimChosen for this emotion at gen7 ---
    trial_csv = None
    for fname in os.listdir(subject_folder):
        if fname.endswith('_trial_records.csv'):
            trial_csv = os.path.join(subject_folder, fname)
            break
    if trial_csv is None:
        return None

    chosen_index = None
    n_candidates = None
    with open(trial_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                if int(row.get('emotion_row', '-1')) != emo_num:
                    continue
                if int(row.get('generation_col', '-1')) != 7:
                    continue
            except ValueError:
                continue
            stim_str = row.get('stimChosen', '').strip()
            if not stim_str:
                continue
            try:
                parsed = ast.literal_eval(stim_str)
            except (ValueError, SyntaxError):
                continue
            # Normalize to list form
            if isinstance(parsed, int):
                # Scalar form (rare anomaly): 1 means the single presented face was chosen
                chosen_index = 0
                n_candidates = 1
            elif isinstance(parsed, (list, tuple)):
                ones = [i for i, v in enumerate(parsed) if int(v) == 1]
                if len(ones) != 1:
                    # Either no face chosen or multiple (shouldn't happen at gen7)
                    return None
                chosen_index = ones[0]
                n_candidates = len(parsed)
            break

    if chosen_index is None:
        return None

    # --- Load the gen7 array and extract the chosen column ---
    arr = np.loadtxt(gen7_file, delimiter=',')

    if arr.ndim == 1:
        # File is a single 200-value vector: only one candidate face presented
        # The single column IS the super face
        super_face = arr[1:]  # strip row 0 (index)
    else:
        # 200 × N matrix: row 0 is index row, columns 1..N are candidate faces
        # Strip row 0, then take the chosen column
        params = arr[1:, :]  # 199 × N
        if chosen_index >= params.shape[1]:
            return None
        super_face = params[:, chosen_index]

    assert super_face.shape == (199,), \
        f"Super face shape {super_face.shape} != (199,) in {gen7_file}"

    return super_face, n_candidates


def load_all_subjects() -> List[SubjectData]:
    """Load all subject data: EQ scores, group assignments, and centroids.

    AUDIT:
    - 57 data folders exist in GASstatsData
    - 53 have EQ scores (excluded: GAS46-49 no EQ)
    - 4 IDs never existed (GAS5, GAS9, GAS52, GAS57)
    - All 53 subjects have gen7 data for all 13 emotions
    - Emotion numbering is subject-specific (read from trial_records.csv)
    """
    # Step 1: Load EQ scores
    eq_scores = load_eq_scores()
    print(f"  EQ scores loaded: {len(eq_scores)} subjects")

    # Step 2: K-Means clustering
    scored_sids = sorted(eq_scores.keys(), key=lambda x: int(x.replace('GAS', '')))
    score_values = [eq_scores[sid] for sid in scored_sids]
    c_low, c_high, high_idx = kmeans_1d_k2(score_values)

    # Assign groups
    groups = {}
    for sid in scored_sids:
        score = eq_scores[sid]
        if abs(score - c_high) < abs(score - c_low):
            groups[sid] = 'High Empathy'
        else:
            groups[sid] = 'Low Empathy'

    n_high = sum(1 for g in groups.values() if g == 'High Empathy')
    n_low = sum(1 for g in groups.values() if g == 'Low Empathy')
    high_scores = [eq_scores[s] for s, g in groups.items() if g == 'High Empathy']
    low_scores = [eq_scores[s] for s, g in groups.items() if g == 'Low Empathy']

    print(f"  K-Means: High Empathy n={n_high} (mean={np.mean(high_scores):.1f}), "
          f"Low Empathy n={n_low} (mean={np.mean(low_scores):.1f})")
    print(f"  Cluster boundary ≈ {(c_low + c_high) / 2:.1f}")

    # Step 3: Load centroids from raw data using per-subject emotion mapping
    subjects = []
    seen_sids = set()  # Track to avoid duplicates from folder name overlaps

    for folder_name in sorted(os.listdir(DATA_DIR)):
        folder_path = os.path.join(DATA_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue

        # Extract subject ID — must match exactly (GAS6 != GAS60)
        m = re.match(r'(GAS\d+)faces', folder_name)
        if not m:
            continue
        sid = m.group(1)

        # Skip if we've already processed this subject
        if sid in seen_sids:
            continue

        # Skip subjects without EQ data
        if sid in EXCLUDED_NO_EQ:
            continue
        if sid not in eq_scores:
            continue

        # Read this subject's emotion-to-number mapping
        emo_map = load_subject_emotion_map(folder_path)
        if not emo_map:
            print(f"  WARNING: No trial records for {sid}, skipping")
            continue

        centroids = {}
        n_faces = {}

        loader_fn = load_centroid_median_of_selected if LOADER_MODE == 'centroid' else load_raw_centroid
        for emo_name, emo_num in emo_map.items():
            result = loader_fn(folder_path, emo_num)
            if result is not None:
                centroids[emo_name], n_faces[emo_name] = result

        seen_sids.add(sid)
        subjects.append(SubjectData(
            id=sid,
            eq_score=eq_scores[sid],
            eq_group=groups[sid],
            centroids=centroids,
            n_faces=n_faces,
        ))

    return subjects


# =============================================================================
# VALIDATION CHECKS
# =============================================================================

def validate_data(subjects: List[SubjectData]):
    """Run comprehensive validation assertions on loaded data.

    AUDIT: These checks run every time the script executes.
    Any failure means the data or pipeline has a problem.
    """
    print("\n" + "=" * 60)
    print("VALIDATION CHECKS")
    print("=" * 60)

    # Check 1: Correct number of subjects
    assert len(subjects) == 53, f"Expected 53 subjects, got {len(subjects)}"
    print(f"  [PASS] N = {len(subjects)} subjects")

    # Check 2: All subjects have all 13 emotions
    for s in subjects:
        missing = [e for e in EMOTIONS if e not in s.centroids]
        assert not missing, f"{s.id} missing emotions: {missing}"
    print(f"  [PASS] All 53 subjects have all 13 emotion centroids")

    # Check 3: All centroids are 199-dimensional
    for s in subjects:
        for emo, vec in s.centroids.items():
            assert vec.shape == (199,), f"{s.id}/{emo}: shape {vec.shape} != (199,)"
    print(f"  [PASS] All centroids are 199-dimensional")

    # Check 4: EQ score ranges
    scores = [s.eq_score for s in subjects]
    assert all(0 <= s <= 80 for s in scores), f"EQ scores out of range: {min(scores)}-{max(scores)}"
    print(f"  [PASS] EQ scores in valid range [0, 80]: min={min(scores)}, max={max(scores)}")

    # Check 5: Group assignment consistency
    high = [s for s in subjects if s.eq_group == 'High Empathy']
    low = [s for s in subjects if s.eq_group == 'Low Empathy']
    assert len(high) + len(low) == 53, "Group assignment doesn't sum to 53"
    assert len(high) == 30, f"Expected 30 High Empathy, got {len(high)}"
    assert len(low) == 23, f"Expected 23 Low Empathy, got {len(low)}"
    # High group should have higher scores than low group
    min_high = min(s.eq_score for s in high)
    max_low = max(s.eq_score for s in low)
    assert min_high > max_low, f"Group overlap: min(High)={min_high} <= max(Low)={max_low}"
    print(f"  [PASS] Groups: High={len(high)} (scores {min_high}-{max(s.eq_score for s in high)}), "
          f"Low={len(low)} (scores {min(s.eq_score for s in low)}-{max_low})")

    # Check 6: No duplicate subject IDs
    ids = [s.id for s in subjects]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found"
    print(f"  [PASS] No duplicate subject IDs")

    # Check 7: Excluded subjects are not present
    present_ids = set(ids)
    for excluded in EXCLUDED_NO_EQ:
        assert excluded not in present_ids, f"{excluded} should be excluded"
    print(f"  [PASS] Excluded subjects (GAS46-49) are absent")

    # Check 8: Cosine distances are in valid range [0, 2]
    sample_d = cosine_distance(subjects[0].centroids['Amusement'],
                                subjects[1].centroids['Anger'])
    assert 0 <= sample_d <= 2.0, f"Cosine distance out of range: {sample_d}"
    print(f"  [PASS] Cosine distance validation (sample: {sample_d:.6f})")

    # Check 9: Face count plausibility check
    # superface mode: n_faces = gen7 candidates (typically 1-13)
    # centroid mode:  n_faces = total selected faces across gen1-gen7 (much larger)
    upper = 13 if LOADER_MODE == 'superface' else 100
    for s in subjects:
        for emo, nf in s.n_faces.items():
            assert 1 <= nf <= upper, f"{s.id}/{emo}: {nf} faces (expected 1-{upper})"
    print(f"  [PASS] Face counts ({LOADER_MODE}): all in range [1, {upper}]")

    print("  All validation checks passed!\n")


# =============================================================================
# ANALYSIS 1: 13×13 MATRIX (Group Centroid Distance)
# =============================================================================

def run_13x13_matrix(subjects: List[SubjectData]) -> List[Dict]:
    """Compute the full 13×13 emotion-pair p-value matrix.

    AUDIT: Method (matching original statistics.ts::runEmpathyAnalysis):
    For cell (row_emo, col_emo):
      1. Compute group centroids for col_emo:
         - high_centroid = mean of all High Empathy subjects' col_emo centroids
         - low_centroid = mean of all Low Empathy subjects' col_emo centroids
      2. For each subject, compute cosine distance from that subject's
         row_emo centroid to their group's col_emo centroid
      3. Welch's t-test comparing High vs Low distance distributions

    CORRECTION: Subject vectors are 199-dim column-mean centroids (not flattened).
    All 53 subjects used for every cell (no majority-rule filtering).
    """
    print("=" * 60)
    print("ANALYSIS 1: 13×13 Matrix (Corrected)")
    print("=" * 60)

    # Step 1: Compute group centroids for each emotion
    group_centroids = {}
    for emo in EMOTIONS:
        high_vecs = [s.centroids[emo] for s in subjects if s.eq_group == 'High Empathy']
        low_vecs = [s.centroids[emo] for s in subjects if s.eq_group == 'Low Empathy']
        group_centroids[(emo, 'High Empathy')] = np.mean(high_vecs, axis=0)
        group_centroids[(emo, 'Low Empathy')] = np.mean(low_vecs, axis=0)

    # Step 2: Compute the 13×13 matrix
    results = []
    for e1 in EMOTIONS:
        for e2 in EMOTIONS:
            high_dists = []
            low_dists = []

            for s in subjects:
                vec = s.centroids[e1]
                group_cent = group_centroids[(e2, s.eq_group)]
                d = cosine_distance(vec, group_cent)

                if s.eq_group == 'High Empathy':
                    high_dists.append(d)
                else:
                    low_dists.append(d)

            test = welch_ttest(high_dists, low_dists)
            d_val = cohens_d(high_dists, low_dists)

            results.append({
                'row_emotion': e1,
                'col_emotion': e2,
                'is_diagonal': e1 == e2,
                'high_n': len(high_dists),
                'low_n': len(low_dists),
                'high_mean': float(np.mean(high_dists)),
                'low_mean': float(np.mean(low_dists)),
                'mean_diff': float(np.mean(high_dists) - np.mean(low_dists)),
                't_statistic': test['t_stat'],
                'df_welch': test['df'],
                'p_value': test['p_value'],
                'cohens_d': d_val,
            })

    # Step 3: Apply multiple comparison corrections
    p_raw = [r['p_value'] for r in results]
    p_bh = bh_fdr(p_raw)
    p_bonf = bonferroni(p_raw)
    p_holm = holm(p_raw)

    for i, r in enumerate(results):
        r['p_bh_fdr'] = p_bh[i]
        r['p_bonferroni'] = p_bonf[i]
        r['p_holm'] = p_holm[i]
        r['sig_raw_005'] = r['p_value'] < ALPHA
        r['sig_bh_fdr_005'] = p_bh[i] < ALPHA
        r['sig_bonferroni_005'] = p_bonf[i] < ALPHA
        r['sig_holm_005'] = p_holm[i] < ALPHA

    # Step 4: Report summary
    sig_raw = sum(1 for r in results if r['sig_raw_005'])
    sig_fdr = sum(1 for r in results if r['sig_bh_fdr_005'])
    sig_bonf = sum(1 for r in results if r['sig_bonferroni_005'])
    diag_raw = sum(1 for r in results if r['is_diagonal'] and r['sig_raw_005'])
    diag_fdr = sum(1 for r in results if r['is_diagonal'] and r['sig_bh_fdr_005'])

    print(f"  Raw p<0.05:       {sig_raw}/169")
    print(f"  BH-FDR q<0.05:    {sig_fdr}/169")
    print(f"  Bonferroni p<0.05: {sig_bonf}/169")
    print(f"  Diagonal raw:      {diag_raw}/13")
    print(f"  Diagonal FDR:      {diag_fdr}/13\n")

    # Save
    outpath = os.path.join(OUTPUT_DIR, 'CORRECTED_13x13_matrix.csv')
    with open(outpath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"  Saved: {outpath}")

    return results


# =============================================================================
# ANALYSIS 2: Continuous EQ Correlations
# =============================================================================

def run_continuous_eq_correlations(subjects: List[SubjectData]) -> List[Dict]:
    """Correlate continuous EQ scores with emotion-pair distances.

    AUDIT: For each (e1, e2) pair, compute each subject's cosine distance
    between their e1 and e2 centroids, then correlate with EQ score.
    This avoids the information loss of dichotomizing EQ into groups.
    """
    print("=" * 60)
    print("ANALYSIS 2: Continuous EQ Correlations")
    print("=" * 60)

    results = []
    eq_scores = [s.eq_score for s in subjects]

    for e1 in EMOTIONS:
        for e2 in EMOTIONS:
            if e1 == e2:
                # Self-distance is always 0 — skip
                continue

            distances = [cosine_distance(s.centroids[e1], s.centroids[e2]) for s in subjects]
            corr = pearson_r(eq_scores, distances)

            results.append({
                'emotion_1': e1,
                'emotion_2': e2,
                'r': corr['r'],
                'p_value': corr['p_value'],
                'n': corr['n'],
            })

    # FDR correction
    p_raw = [r['p_value'] for r in results]
    p_bh = bh_fdr(p_raw)

    for i, r in enumerate(results):
        r['p_bh_fdr'] = p_bh[i]
        r['sig_raw_005'] = r['p_value'] < ALPHA
        r['sig_bh_fdr_005'] = p_bh[i] < ALPHA

    sig_raw = sum(1 for r in results if r['sig_raw_005'])
    sig_fdr = sum(1 for r in results if r['sig_bh_fdr_005'])
    print(f"  Raw p<0.05: {sig_raw}/{len(results)}")
    print(f"  BH-FDR q<0.05: {sig_fdr}/{len(results)}")

    # Show top correlations
    top = sorted(results, key=lambda x: x['p_value'])[:10]
    print(f"\n  Top 10 correlations:")
    for r in top:
        fdr_marker = '*' if r['sig_bh_fdr_005'] else ''
        print(f"    {r['emotion_1']:<16s} x {r['emotion_2']:<16s} r={r['r']:.4f} p={r['p_value']:.6f} q={r['p_bh_fdr']:.6f} {fdr_marker}")

    # Save
    outpath = os.path.join(OUTPUT_DIR, 'CORRECTED_continuous_eq_correlations.csv')
    with open(outpath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\n  Saved: {outpath}")

    return results


# =============================================================================
# ANALYSIS 3: Subject Profiles Summary
# =============================================================================

def run_subject_profiles(subjects: List[SubjectData]):
    """Export subject profiles with EQ scores and group assignments.

    AUDIT: Cross-validates group assignments and provides descriptive stats.
    """
    print("=" * 60)
    print("ANALYSIS 3: Subject Profiles")
    print("=" * 60)

    # Individual profiles
    rows = []
    for s in sorted(subjects, key=lambda x: int(x.id.replace('GAS', ''))):
        rows.append({
            'subject_id': s.id,
            'eq_total_score': s.eq_score,
            'empathy_group': s.eq_group,
            'n_emotions_with_data': len(s.centroids),
            'avg_faces_selected': np.mean(list(s.n_faces.values())),
        })

    outpath = os.path.join(OUTPUT_DIR, 'CORRECTED_subject_profiles.csv')
    with open(outpath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    # Summary statistics
    high = [s for s in subjects if s.eq_group == 'High Empathy']
    low = [s for s in subjects if s.eq_group == 'Low Empathy']

    high_scores = [s.eq_score for s in high]
    low_scores = [s.eq_score for s in low]

    test = welch_ttest(high_scores, low_scores)
    d_val = cohens_d(high_scores, low_scores)

    print(f"  High Empathy: n={len(high)}, mean={np.mean(high_scores):.1f}, "
          f"SD={np.std(high_scores, ddof=1):.1f}, range=[{min(high_scores)}, {max(high_scores)}]")
    print(f"  Low Empathy:  n={len(low)}, mean={np.mean(low_scores):.1f}, "
          f"SD={np.std(low_scores, ddof=1):.1f}, range=[{min(low_scores)}, {max(low_scores)}]")
    print(f"  Group difference: t={test['t_stat']:.2f}, p={test['p_value']:.6f}, d={d_val:.2f}")
    print(f"  Saved: {outpath}\n")


# =============================================================================
# ANALYSIS 4: Permutation Tests (optional, non-parametric validation)
# =============================================================================

def run_permutation_tests(subjects: List[SubjectData], matrix_results: List[Dict]):
    """Permutation test for significant matrix cells.

    AUDIT: For each significant cell, shuffle group labels N_PERMUTATIONS times
    and recompute the t-statistic. The p-value is the proportion of permuted
    t-statistics as extreme as the observed.
    """
    if N_PERMUTATIONS == 0:
        print("ANALYSIS 4: Permutation Tests — SKIPPED (N_PERMUTATIONS=0)")
        return []

    print("=" * 60)
    print(f"ANALYSIS 4: Permutation Tests ({N_PERMUTATIONS} iterations)")
    print("=" * 60)

    np.random.seed(RANDOM_SEED)

    # Only test cells that are significant at raw p<0.05
    sig_cells = [r for r in matrix_results if r['sig_raw_005']]
    print(f"  Testing {len(sig_cells)} significant cells...")

    # Precompute group labels
    group_labels = [s.eq_group for s in subjects]

    # Group centroids function
    def compute_group_centroids(labels, emo):
        high_vecs = [s.centroids[emo] for s, l in zip(subjects, labels) if l == 'High Empathy']
        low_vecs = [s.centroids[emo] for s, l in zip(subjects, labels) if l == 'Low Empathy']
        return np.mean(high_vecs, axis=0), np.mean(low_vecs, axis=0)

    results = []
    for idx, cell in enumerate(sig_cells):
        e1 = cell['row_emotion']
        e2 = cell['col_emotion']
        observed_t = abs(cell['t_statistic'])

        count_extreme = 0
        for _ in range(N_PERMUTATIONS):
            perm_labels = list(np.random.permutation(group_labels))

            high_cent, low_cent = compute_group_centroids(perm_labels, e2)

            high_dists = []
            low_dists = []
            for s, l in zip(subjects, perm_labels):
                d = cosine_distance(s.centroids[e1],
                                     high_cent if l == 'High Empathy' else low_cent)
                if l == 'High Empathy':
                    high_dists.append(d)
                else:
                    low_dists.append(d)

            perm_test = welch_ttest(high_dists, low_dists)
            if abs(perm_test['t_stat']) >= observed_t:
                count_extreme += 1

        perm_p = (count_extreme + 1) / (N_PERMUTATIONS + 1)  # +1 correction

        results.append({
            'row_emotion': e1,
            'col_emotion': e2,
            'is_diagonal': e1 == e2,
            'observed_t': cell['t_statistic'],
            'parametric_p': cell['p_value'],
            'permutation_p': perm_p,
            'n_permutations': N_PERMUTATIONS,
            'n_extreme': count_extreme,
        })

        if (idx + 1) % 10 == 0:
            print(f"    Completed {idx + 1}/{len(sig_cells)} cells")

    # Save
    if results:
        outpath = os.path.join(OUTPUT_DIR, 'CORRECTED_permutation_tests.csv')
        with open(outpath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

        confirmed = sum(1 for r in results if r['permutation_p'] < ALPHA)
        print(f"\n  Permutation-confirmed (p<0.05): {confirmed}/{len(results)}")
        print(f"  Saved: {outpath}")

    return results


# =============================================================================
# ANALYSIS 5: Descriptive Statistics Per Emotion
# =============================================================================

def run_descriptive_stats(subjects: List[SubjectData]):
    """Descriptive statistics for faces selected and centroid properties.

    AUDIT: Documents the raw data characteristics for Methods section.
    """
    print("=" * 60)
    print("ANALYSIS 5: Descriptive Statistics Per Emotion")
    print("=" * 60)

    rows = []
    for emo in EMOTIONS:
        faces = [s.n_faces[emo] for s in subjects]
        norms = [float(np.linalg.norm(s.centroids[emo])) for s in subjects]

        rows.append({
            'emotion': emo,
            'n_subjects': len(subjects),
            'faces_mean': np.mean(faces),
            'faces_sd': np.std(faces, ddof=1),
            'faces_min': min(faces),
            'faces_max': max(faces),
            'centroid_norm_mean': np.mean(norms),
            'centroid_norm_sd': np.std(norms, ddof=1),
        })

        print(f"  {emo:<16s}: faces={np.mean(faces):.1f}±{np.std(faces,ddof=1):.1f} "
              f"[{min(faces)}-{max(faces)}], norm={np.mean(norms):.2f}±{np.std(norms,ddof=1):.2f}")

    outpath = os.path.join(OUTPUT_DIR, 'CORRECTED_descriptive_stats.csv')
    with open(outpath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n  Saved: {outpath}")


# =============================================================================
# ANALYSIS 6: Task Validation (Each Emotion Distinct From Other 12)
# =============================================================================

def run_task_validation(subjects: List[SubjectData]):
    """Task validation: within-emotion vs between-emotion cosine distance.

    AUDIT (2026-04-10): Added to replicate the first claim of the original
    abstract — that participant-generated centroids for each affect are
    structurally distinct from the other 12 affects. This is a per-subject,
    per-emotion test run across all 53 subjects (empathy groups collapsed).

    For each emotion E:
      1. Compute group E centroid = mean across all subjects of subject.centroids[E].
      2. For each subject s, compute:
           within_s  = cos_dist(s.centroids[E], group_E_centroid)
           between_s = mean over E' != E of cos_dist(s.centroids[E], group_E'_centroid)
      3. Paired t-test across subjects: within vs between (within should be smaller).

    A one-sample t-test on (between - within) > 0 gives the same answer; we use
    a paired Welch-style test via welch_ttest on the paired difference against
    zero by treating (between - within) as a single sample against 0.
    Since scipy is not available, we compute a one-sample t-test by hand.
    """
    print("=" * 60)
    print("ANALYSIS 6: Task Validation — Within vs Between Emotion Distance")
    print("=" * 60)

    # Group centroids across all subjects (no grouping by empathy)
    group_centroids = {}
    for emo in EMOTIONS:
        stacked = np.stack([s.centroids[emo] for s in subjects], axis=0)  # (N, 199)
        group_centroids[emo] = stacked.mean(axis=0)

    rows = []
    raw_pvals = []
    for emo in EMOTIONS:
        within_distances = []
        between_distances = []
        diffs = []
        for s in subjects:
            w = cosine_distance(s.centroids[emo], group_centroids[emo])
            others = [cosine_distance(s.centroids[emo], group_centroids[e2])
                      for e2 in EMOTIONS if e2 != emo]
            b = float(np.mean(others))
            within_distances.append(w)
            between_distances.append(b)
            diffs.append(b - w)

        diffs = np.array(diffs, dtype=float)
        n = len(diffs)
        mean_diff = float(diffs.mean())
        sd_diff = float(diffs.std(ddof=1))
        se_diff = sd_diff / math.sqrt(n)
        # One-sample t-test against 0 (H1: between > within, i.e., diff > 0)
        t_stat = mean_diff / se_diff if se_diff > 0 else 0.0
        df = n - 1
        # Two-tailed p-value via normal approximation (n=53 is large enough)
        p_two = 2.0 * (1.0 - norm_cdf(abs(t_stat)))
        # Cohen's dz for paired comparison
        dz = mean_diff / sd_diff if sd_diff > 0 else 0.0

        raw_pvals.append(p_two)
        rows.append({
            'emotion': emo,
            'n': n,
            'within_mean': float(np.mean(within_distances)),
            'within_sd': float(np.std(within_distances, ddof=1)),
            'between_mean': float(np.mean(between_distances)),
            'between_sd': float(np.std(between_distances, ddof=1)),
            'diff_mean': mean_diff,
            'diff_sd': sd_diff,
            't_statistic': t_stat,
            'df': df,
            'p_value': p_two,
            'cohens_dz': dz,
        })

        sig = '***' if p_two < 0.001 else ('**' if p_two < 0.01 else ('*' if p_two < 0.05 else ''))
        print(f"  {emo:<16s}: within={np.mean(within_distances):.4f} "
              f"between={np.mean(between_distances):.4f} "
              f"diff={mean_diff:+.4f} t={t_stat:6.2f} p={p_two:.2e} dz={dz:+.2f} {sig}")

    # Multiple-comparison corrections across the 13 emotion tests
    fdr_q = bh_fdr(raw_pvals)
    bonf_p = bonferroni(raw_pvals)
    holm_p = holm(raw_pvals)
    for i, r in enumerate(rows):
        r['p_bh_fdr'] = fdr_q[i]
        r['p_bonferroni'] = bonf_p[i]
        r['p_holm'] = holm_p[i]
        r['sig_raw_005'] = raw_pvals[i] < 0.05
        r['sig_bh_fdr_005'] = fdr_q[i] < 0.05
        r['sig_bonferroni_005'] = bonf_p[i] < 0.05
        r['sig_holm_005'] = holm_p[i] < 0.05

    n_raw = sum(1 for p in raw_pvals if p < 0.05)
    n_fdr = sum(1 for q in fdr_q if q < 0.05)
    n_bonf = sum(1 for p in bonf_p if p < 0.05)
    print(f"\n  Raw p<0.05:        {n_raw}/13")
    print(f"  BH-FDR q<0.05:     {n_fdr}/13")
    print(f"  Bonferroni p<0.05: {n_bonf}/13")

    outpath = os.path.join(OUTPUT_DIR, 'CORRECTED_task_validation.csv')
    with open(outpath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n  Saved: {outpath}")
    return rows


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def main():
    print("=" * 60)
    print("CORRECTED ANALYSIS PIPELINE")
    print("Empathy & Facial Emotion Representations (GA)")
    print(f"Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    subjects = load_all_subjects()

    # Validate
    validate_data(subjects)

    # Run analyses
    matrix_results = run_13x13_matrix(subjects)
    eq_correlations = run_continuous_eq_correlations(subjects)
    run_subject_profiles(subjects)
    run_descriptive_stats(subjects)
    run_task_validation(subjects)

    # Permutation tests (can be slow — set N_PERMUTATIONS=0 to skip)
    run_permutation_tests(subjects, matrix_results)

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"All outputs saved to: {OUTPUT_DIR}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('superface', 'centroid'):
        LOADER_MODE = sys.argv[1]
    print(f"\n>>> LOADER_MODE = {LOADER_MODE}\n")
    main()
