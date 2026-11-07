"""
Data loaders for the genetic-algorithm face task (Cui & Bex).

Reads participant folders (trial records + raw_arrays/shapeVals_emo{N}_gen{G}.csv), Empathy Quotient responses,
and builds one 199-dimensional prototype per participant and affect. Paths are set by revision_analysis.py.
"""
import os, csv, re, ast
from typing import Dict, List, Optional, Tuple, NamedTuple
import numpy as np

DATA_DIR = os.path.join('data', 'GASstatsData')
EQ_CSV = os.path.join('data', 'Empathy Quotient Questionnaire (BC 2024) (Responses).csv')

EMO_NUM_TO_NAME = {
    1: 'Embarrassment', 2: 'Awe', 3: 'Sadness', 4: 'Fear', 5: 'Happiness',
    6: 'Disgust', 7: 'Amusement', 8: 'Anger', 9: 'Contempt', 10: 'Surprise',
    11: 'Interest', 12: 'Pride', 13: 'Shame'
}
EMOTIONS = sorted(EMO_NUM_TO_NAME.values())

# EQ items (1-indexed): positively and negatively keyed; remaining items are fillers
EQ_POSITIVE_INDICES = [1, 6, 19, 22, 25, 26, 35, 36, 37, 38, 41, 42, 43, 44, 52, 54, 55, 57, 58, 59, 60]
EQ_NEGATIVE_INDICES = [4, 8, 10, 11, 12, 14, 15, 18, 21, 27, 28, 29, 32, 34, 39, 46, 48, 49, 50]

EXCLUDED_NO_EQ = {'GAS46', 'GAS47', 'GAS48', 'GAS49'}   # completed the task but not the EQ
LOADER_MODE = 'centroid'


class SubjectData(NamedTuple):
    """All data for one subject."""
    id: str
    eq_score: int
    eq_group: str  # 'High Empathy' or 'Low Empathy'
    centroids: Dict[str, np.ndarray]  # emotion -> 199-dim centroid vector
    n_faces: Dict[str, int]


def load_eq_scores() -> Dict[str, int]:
    """Load EQ totals (Baron-Cohen & Wheelwright, 2004): 2/1 points for strong/mild empathic responses on 40 scored items; 20 fillers ignored. Range 0-80."""
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
    """One-dimensional k-means with k = 2, initialized at the minimum and maximum scores. Returns (low centroid, high centroid, index of high cluster)."""
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
    """Map each affect name to its block number for one participant (affect order was randomized per participant)."""
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
    """Prototype for one participant and affect: coefficient-wise median of all faces selected in generations 1-7 (199 Basel shape coefficients). Returns (prototype, number of selected faces) or None."""
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


def load_all_subjects() -> List[SubjectData]:
    """Load EQ scores, k-means EQ groups and per-affect prototypes for every participant with EQ data."""
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

        loader_fn = load_centroid_median_of_selected
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
