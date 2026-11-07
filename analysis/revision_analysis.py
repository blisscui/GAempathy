#!/usr/bin/env python3
"""
revision_analysis.py — single source for every number in the revised manuscript
(Scientific Reports major revision, Nov 2026).

Inputs : GASuper-Empathy-Stats-Replication/python_stats/data (face-task + EQ),
         demographics xlsx, BDI-II (GASdepressionStats parser; used only as covariate).
Outputs: final/results.json, final/results_summary.txt, final/*.csv (figure data).

Key conventions
- Prototype (centroid): element-wise median of all faces a participant selected (gen 1–7) for an affect;
  199 Basel Face Model SHAPE coefficients (texture was not varied in the task).
- Every reference prototype EXCLUDES the participant being compared (leave-one-out).
- Distances: cosine distance; Euclidean as robustness check.
- Inference: permutation tests (seed 42); family-wise control by max-statistic permutation;
  Bayes factors (Jeffreys uniform prior on rho, Fisher-z likelihood) and 90% CIs for nulls.
"""
import sys, os, io, csv, json, ast, re, contextlib
import numpy as np
from scipy import stats, integrate

# ---- paths (data available from the corresponding author on reasonable request) ----
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get('GA_DATA_ROOT', os.path.join(HERE, '..', 'data'))   # folder holding the files below
OUT = os.environ.get('GA_OUT', os.path.join(HERE, 'final')); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
import corrected_analysis as ca                    # loaders: EQ scoring, prototypes (median of selected faces)
ca.DATA_DIR = os.path.join(DATA, 'GASstatsData')
ca.EQ_CSV = os.path.join(DATA, 'Empathy Quotient Questionnaire (BC 2024) (Responses).csv')
DEMO_XLSX = os.path.join(DATA, 'Demographic Mental Health + Ocular Health Questionnaire (BC 2024) (Responses) (1).xlsx')
BDI_CSV = os.path.join(DATA, 'bdi_totals.csv')     # two columns: subject_id, bdi_total
import openpyxl

NP = int(os.environ.get('NPERM', 5000)); SEED = 42
rng = np.random.default_rng(SEED)
R = {}                                             # results dict -> JSON
def put(k, v): R[k] = v; return v

# ---------------------------------------------------------------- data
ca.LOADER_MODE = 'centroid'
with contextlib.redirect_stdout(io.StringIO()):
    S = ca.load_all_subjects()
    pass
norm_id = lambda k: (lambda s: 'GAS' + str(int(s[3:])) if s[3:].isdigit() else s)(str(k).strip().upper().replace(' ', ''))
bdi = {norm_id(r['subject_id']): float(r['bdi_total']) for r in csv.DictReader(open(BDI_CSV))}
wb = openpyxl.load_workbook(DEMO_XLSX, read_only=True)
dem = {norm_id(r[2]): (r[3], r[6]) for r in list(wb.active.iter_rows(values_only=True))[1:] if r[2]}
E = ca.EMOTIONS; K = len(E); N = len(S)
X = np.array([[s.centroids[e] for e in E] for s in S])          # N x 13 x 199
eq = np.array([s.eq_score for s in S], float)
hi = np.array([s.eq_group == 'High Empathy' for s in S])
nf = np.array([[s.n_faces[e] for e in E] for s in S])
sex_m = np.array([1.0 if str(dem[s.id][1]).lower().startswith('m') else 0.0 for s in S])
age = np.array([float(dem[s.id][0]) for s in S])
dep = np.array([bdi[s.id] for s in S], float)
iu = np.triu_indices(K, 1); PAIRS = [(E[a], E[b]) for a, b in zip(*iu)]
iA, iC = E.index('Amusement'), E.index('Contempt')

# per-face stacks for split-half reliability (same selection logic as ca.load_centroid_median_of_selected)
def load_stack(folder, emo_num):
    trial = [f for f in os.listdir(folder) if f.endswith('_trial_records.csv')][0]
    cols = []
    for row in csv.DictReader(open(os.path.join(folder, trial))):
        try:
            if int(row.get('emotion_row', -1)) != emo_num: continue
            g = int(row.get('generation_col', -1))
        except ValueError: continue
        if not 1 <= g <= 7: continue
        st = row.get('stimChosen', '').strip()
        if not st: continue
        p = ast.literal_eval(st)
        idx = ([0] if int(p) == 1 else []) if isinstance(p, int) else [i for i, v in enumerate(p) if int(v) == 1]
        if not idx: continue
        a = np.loadtxt(os.path.join(folder, 'raw_arrays', f'shapeVals_emo{emo_num}_gen{g}.csv'), delimiter=',')
        a = a[1:][:, None] if a.ndim == 1 else a[1:, :]
        cols += [a[:, i] for i in idx if i < a.shape[1]]
    return np.column_stack(cols)
folders = {re.match(r'(GAS\d+)faces', f).group(1): os.path.join(ca.DATA_DIR, f)
           for f in sorted(os.listdir(ca.DATA_DIR)) if re.match(r'(GAS\d+)faces', f)}
STACK = [[load_stack(folders[s.id], ca.load_subject_emotion_map(folders[s.id])[e]) for e in E] for s in S]
assert all(np.allclose(np.median(STACK[i][k], 1), X[i, k]) for i in range(N) for k in range(K)), 'loader mismatch'

# ---------------------------------------------------------------- helpers
def cosd(a, b): return 1 - np.sum(a * b, -1) / (np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1))
def eucd(a, b): return np.linalg.norm(a - b, axis=-1)
LOO = np.stack([np.delete(X, i, 0).mean(0) for i in range(N)])  # N x 13 x 199, everyone-else prototypes
def d_pooled(a, b):
    sp = np.sqrt(((len(a)-1)*a.var(ddof=1) + (len(b)-1)*b.var(ddof=1)) / (len(a)+len(b)-2)); return (a.mean()-b.mean())/sp
def bf10_r(r, n):
    z = np.arctanh(r); s = 1/np.sqrt(n-3); L = lambda p: stats.norm.pdf(z, np.arctanh(p), s)
    return integrate.quad(lambda p: L(p)*0.5, -0.999, 0.999)[0] / L(0)
def ci90(r, n): z = np.arctanh(r); s = 1/np.sqrt(n-3); return float(np.tanh(z-1.645*s)), float(np.tanh(z+1.645*s))
def ci95(r, n): z = np.arctanh(r); s = 1/np.sqrt(n-3); return float(np.tanh(z-1.96*s)), float(np.tanh(z+1.96*s))
def perm_r(x, y):
    r0 = stats.pearsonr(x, y)[0]; nl = np.array([stats.pearsonr(rng.permutation(x), y)[0] for _ in range(NP)])
    return float((np.sum(np.abs(nl) >= abs(r0)) + 1) / (NP + 1))
def zs(v): return (v - v.mean()) / v.std()
COV = [sex_m, zs(age), zs(dep), zs(nf.mean(1))]
def partial_r(y, x, covs=COV):
    Z = np.column_stack([np.ones(N)] + covs)
    ry = y - Z @ np.linalg.lstsq(Z, y, rcond=None)[0]; rx = x - Z @ np.linalg.lstsq(Z, x, rcond=None)[0]
    r = stats.pearsonr(rx, ry)[0]; df = N - 2 - len(covs); t = r*np.sqrt(df/(1-r*r))
    return float(r), float(2*stats.t.sf(abs(t), df))
def eq_test(name, score):
    r, p = stats.pearsonr(eq, score); rho, prho = stats.spearmanr(eq, score); pr, pp = partial_r(score, eq)
    t, pg = stats.ttest_ind(score[hi], score[~hi], equal_var=False); bf = bf10_r(r, N)
    out = dict(r=float(r), p=float(p), p_perm=perm_r(eq, score), ci95=ci95(r, N), ci90=ci90(r, N),
               spearman=float(rho), p_spearman=float(prho), partial_r=pr, partial_p=pp,
               BF10=float(bf), BF01=float(1/bf), group_t=float(t), group_p=float(pg),
               group_d=float(d_pooled(score[hi], score[~hi])))
    return put(name, out)

# ---------------------------------------------------------------- 1. sample
put('sample', dict(N=N, n_women=int((sex_m == 0).sum()), n_men=int(sex_m.sum()), age_mean=float(age.mean()),
    age_sd=float(age.std(ddof=1)), age_range=[float(age.min()), float(age.max())],
    EQ_mean=float(eq.mean()), EQ_sd=float(eq.std(ddof=1)), EQ_range=[float(eq.min()), float(eq.max())],
    EQ_shapiro_p=float(stats.shapiro(eq).pvalue), n_hi=int(hi.sum()), n_lo=int((~hi).sum()),
    EQ_hi_mean=float(eq[hi].mean()), EQ_lo_mean=float(eq[~hi].mean()),
    kmeans_boundary=float((eq[hi].mean() + eq[~hi].mean())/2), EQ_median=float(np.median(eq)),
    nfaces_median=float(np.median(nf)), nfaces_range=[int(nf.min()), int(nf.max())]))
t = stats.ttest_ind(eq[sex_m == 0], eq[sex_m == 1], equal_var=False)
put('EQ_by_sex', dict(women=float(eq[sex_m == 0].mean()), women_sd=float(eq[sex_m == 0].std(ddof=1)),
    men=float(eq[sex_m == 1].mean()), men_sd=float(eq[sex_m == 1].std(ddof=1)), t=float(t.statistic), df=float(t.df), p=float(t.pvalue),
    d=float(d_pooled(eq[sex_m == 0], eq[sex_m == 1]))))
put('EQ_BDI', dict(zip(['r', 'p'], map(float, stats.pearsonr(eq, dep))), BDI_mean=float(dep.mean()), BDI_sd=float(dep.std(ddof=1))))
put('EQ_age', dict(zip(['r', 'p'], map(float, stats.pearsonr(eq, age)))))
put('EQ_nfaces', dict(zip(['r', 'p'], map(float, stats.pearsonr(eq, nf.mean(1))))))

# ---------------------------------------------------------------- 2. task validation (leave-one-out)
TV = []
for k, e in enumerate(E):
    w = cosd(X[:, k], LOO[:, k])
    b = np.mean([cosd(X[:, k], LOO[:, j]) for j in range(K) if j != k], 0)
    diff = b - w; t, p = stats.ttest_rel(b, w); dz = diff.mean()/diff.std(ddof=1)
    se = np.sqrt(1/N + dz**2/(2*N))
    TV.append(dict(affect=e, within=float(w.mean()), between=float(b.mean()), diff=float(diff.mean()), t=float(t),
                   p=float(p), p_bonf=float(min(1, p*K)), dz=float(dz), dz_lo=float(dz-1.96*se), dz_hi=float(dz+1.96*se)))
put('task_validation', TV)
acc = np.array([np.mean([np.argmin(cosd(X[i, k][None], LOO[i])) == k for k in range(K)]) for i in range(N)])
null = np.array([np.mean([np.argmin(cosd(X[i, k][None], LOO[i][rng.permutation(K)])) == k for i in range(N) for k in range(K)]) for _ in range(1000)])
put('decoding', dict(acc_mean=float(acc.mean()), acc_sd=float(acc.std(ddof=1)), chance=1/K,
    p_perm=float((np.sum(null >= acc.mean()) + 1)/1001), t_vs_chance=float(stats.ttest_1samp(acc, 1/K).statistic),
    p_vs_chance=float(stats.ttest_1samp(acc, 1/K).pvalue),
    per_affect={e: float(np.mean([np.argmin(cosd(X[i, k][None], LOO[i])) == k for i in range(N)])) for k, e in enumerate(E)}))

# ---------------------------------------------------------------- 3. prototype reliability (split-half)
SH = np.zeros((N, K)); XH = np.zeros((N, K))
halves = [[(np.median(st[:, 0::2], 1), np.median(st[:, 1::2], 1)) for st in row] for row in STACK]
for i in range(N):
    for k in range(K):
        a, b = halves[i][k]; SH[i, k] = 1 - cosd(a, b)
        XH[i, k] = np.mean([1 - cosd(a, halves[j][k][1]) for j in range(N) if j != i])
put('reliability', dict(within_person_split_half_cos_sim=float(SH.mean()), between_person_same_affect_cos_sim=float(XH.mean()),
    paired_t=float(stats.ttest_rel(SH.mean(1), XH.mean(1)).statistic), paired_p=float(stats.ttest_rel(SH.mean(1), XH.mean(1)).pvalue),
    dz=float(np.mean(SH.mean(1)-XH.mean(1))/np.std(SH.mean(1)-XH.mean(1), ddof=1)),
    per_affect={e: float(SH[:, k].mean()) for k, e in enumerate(E)},
    r_nfaces=float(stats.pearsonr(nf.ravel(), SH.ravel())[0]),
    r_EQ=float(stats.pearsonr(eq, SH.mean(1))[0]), p_EQ=float(stats.pearsonr(eq, SH.mean(1))[1])))
REL = SH.mean(1)

# ---------------------------------------------------------------- 4. person-level empathy tests
TY = cosd(X, LOO)                                                    # typicality (lower = more typical)
eq_test('typicality', TY.mean(1))
put('typicality_per_affect', [dict(affect=e, r=float(stats.pearsonr(eq, TY[:, k])[0]), p=float(stats.pearsonr(eq, TY[:, k])[1])) for k, e in enumerate(E)])
W = np.stack([cosd(X[i][:, None], X[i][None])[iu] for i in range(N)])  # N x 78 own geometry
eq_test('granularity', W.mean(1))
Wloo = np.stack([np.delete(W, i, 0).mean(0) for i in range(N)])
conv = np.array([stats.spearmanr(W[i], Wloo[i])[0] for i in range(N)])
eq_test('geometry_conventionality', conv)
eq_test('decoding_accuracy', acc)
eq_test('reliability_EQ', REL)
RS = stats.spearmanr(W.T)[0]; tu = np.triu_indices(N, 1); isc = RS[tu]
def mantel(fn):
    o = stats.spearmanr(fn(eq)[tu], isc)[0]
    nl = np.array([stats.spearmanr(fn(rng.permutation(eq))[tu], isc)[0] for _ in range(NP)])
    return dict(rho=float(o), p_perm=float((np.sum(np.abs(nl) >= abs(o)) + 1)/(NP + 1)))
put('intersubject', dict(mean_similarity=float(isc.mean()), sd=float(isc.std()),
    anna_karenina=mantel(lambda v: np.minimum.outer(v, v)), nearest_neighbour=mantel(lambda v: -np.abs(np.subtract.outer(v, v)))))
for nm, sc in [('typicality', TY.mean(1)), ('granularity', W.mean(1)), ('geometry_conventionality', conv)]:
    R[nm]['partial_with_reliability'] = partial_r(sc, eq, COV + [zs(REL)])
put('BDI_vs_measures', {nm: dict(zip(['r', 'p'], map(float, stats.pearsonr(dep, sc)))) for nm, sc in
    [('typicality', TY.mean(1)), ('granularity', W.mean(1)), ('geometry_conventionality', conv), ('decoding_accuracy', acc)]})
pd_ = [R['typicality']['p'], R['intersubject']['anna_karenina']['p_perm'], R['granularity']['p'], R['geometry_conventionality']['p']]
put('primary_family_BY', [float(min(1, p)) for p in stats.false_discovery_control(pd_, method='by')])  # conservative check

# ---------------------------------------------------------------- 5. reference-frame analysis (original 156-cell matrix)
def dist_matrix(mode, labels=hi, metric=cosd):
    D = np.zeros((N, K, K))
    for i in range(N):
        if mode == 'within': ref = X[i]
        else:
            m = np.ones(N, bool) if mode == 'global_loo' else (labels == labels[i]).copy()
            if mode != 'group_incl': m[i] = False
            ref = X[m].mean(0)
        D[i] = metric(X[i][:, None], ref[None])
    return D
def tmat(D, lab):
    a, b = D[lab], D[~lab]; return (a.mean(0)-b.mean(0)) / np.sqrt(a.var(0, ddof=1)/len(a) + b.var(0, ddof=1)/len(b))
def dmat(D, lab):
    a, b = D[lab], D[~lab]; n1, n2 = len(a), len(b)
    sp = np.sqrt(((n1-1)*a.var(0, ddof=1) + (n2-1)*b.var(0, ddof=1))/(n1+n2-2)); return (a.mean(0)-b.mean(0))/sp
off = ~np.eye(K, dtype=bool)
RF = {}
for mode in ['group_incl', 'group_loo', 'global_loo', 'within']:
    for mname, met in [('cosine', cosd), ('euclidean', eucd)]:
        D = dist_matrix(mode, metric=met); y = D[:, iA, iC]; a, b = y[hi], y[~hi]
        t, p = stats.ttest_ind(a, b, equal_var=False); r, pr = stats.pearsonr(eq, y)
        P = np.array([stats.ttest_ind(D[hi, j, k], D[~hi, j, k], equal_var=False).pvalue for j in range(K) for k in range(K) if j != k])
        RF[f'{mode}|{mname}'] = dict(hi=float(a.mean()), lo=float(b.mean()), t=float(t), p=float(p), d=float(d_pooled(a, b)),
            r_EQ=float(r), p_EQ=float(pr), BF01_r=float(1/bf10_r(r, N)), cells_p05=int((P < .05).sum()), min_p=float(P.min()))
put('reference_frames_AxC', RF)
D0 = dist_matrix('group_incl'); DG = dist_matrix('global_loo')
np.savetxt(os.path.join(OUT, 'fig3_d_original.csv'), dmat(D0, hi), delimiter=',', header=','.join(E))
np.savetxt(os.path.join(OUT, 'fig3_d_common.csv'), dmat(DG, hi), delimiter=',', header=','.join(E))
T0 = np.abs(tmat(D0, hi)[off]); TG = np.abs(tmat(DG, hi)[off]); mx0, mxG = [], []
for _ in range(NP):
    p = rng.permutation(hi); mx0.append(np.abs(tmat(dist_matrix('group_incl', labels=p), p)[off]).max())
    mxG.append(np.abs(tmat(DG, p)[off]).max())                          # common reference does not depend on labels
mx0, mxG = np.array(mx0), np.array(mxG)
fw0 = np.array([(np.sum(mx0 >= v)+1)/(NP+1) for v in T0]); fwG = np.array([(np.sum(mxG >= v)+1)/(NP+1) for v in TG])
kAC_off = [n for n, (j, k) in enumerate([(j, k) for j in range(K) for k in range(K) if j != k]) if (j, k) == (iA, iC)][0]
put('maxT_original', dict(AxC_fwer=float(fw0[kAC_off]), n_cells_fwer05=int((fw0 < .05).sum()), max_t=float(T0.max())))
put('maxT_common', dict(AxC_fwer=float(fwG[kAC_off]), n_cells_fwer05=int((fwG < .05).sum()), max_t=float(TG.max())))
a, b = D0[hi, iA, iC], D0[~hi, iA, iC]
bs = [d_pooled(rng.choice(a, len(a)), rng.choice(b, len(b))) for _ in range(NP)]
put('original_AxC_d_ci', dict(d=float(d_pooled(a, b)), ci=[float(x) for x in np.percentile(bs, [2.5, 97.5])]))

# ---------------------------------------------------------------- 6. group-level consensus prototypes (exploratory)
def gp(m): return X[m].mean(0)
def geo(m): P = gp(m); return cosd(P[:, None], P[None])[iu]
obs = cosd(gp(hi), gp(~hi)); nl = np.array([cosd(gp(p), gp(~p)) for p in (rng.permutation(hi) for _ in range(NP))])
put('consensus_per_affect', [dict(affect=e, dist=float(obs[k]), p_raw=float((np.sum(nl[:, k] >= obs[k])+1)/(NP+1)),
    p_fwer=float((np.sum(nl.max(1) >= obs[k])+1)/(NP+1)), null_mean=float(nl[:, k].mean())) for k, e in enumerate(E)])
dobs = geo(hi) - geo(~hi); nl2 = np.array([geo(p) - geo(~p) for p in (rng.permutation(hi) for _ in range(NP))])
kAC = PAIRS.index(('Amusement', 'Contempt'))
put('consensus_geometry', dict(rho_hi_lo=float(stats.spearmanr(geo(hi), geo(~hi))[0]),
    AxC=dict(diff=float(dobs[kAC]), hi=float(geo(hi)[kAC]), lo=float(geo(~hi)[kAC]),
             p_raw=float((np.sum(np.abs(nl2[:, kAC]) >= abs(dobs[kAC]))+1)/(NP+1)),
             p_fwer=float((np.sum(np.abs(nl2).max(1) >= abs(dobs[kAC]))+1)/(NP+1))),
    top=[dict(pair=PAIRS[k], diff=float(dobs[k]), p_raw=float((np.sum(np.abs(nl2[:, k]) >= abs(dobs[k]))+1)/(NP+1)),
              p_fwer=float((np.sum(np.abs(nl2).max(1) >= abs(dobs[k]))+1)/(NP+1))) for k in np.argsort(-np.abs(dobs))[:5]]))
def split_test(g1, g2):
    idx = np.where(g1 | g2)[0]; lab = g1[idx]
    def d(l): A = np.zeros(N, bool); B = np.zeros(N, bool); A[idx[l]] = True; B[idx[~l]] = True; return geo(A) - geo(B)
    o = d(lab); n = np.array([d(rng.permutation(lab)) for _ in range(NP)])
    return dict(n1=int(g1.sum()), n2=int(g2.sum()), diff=float(o[kAC]),
                p_raw=float((np.sum(np.abs(n[:, kAC]) >= abs(o[kAC]))+1)/(NP+1)),
                p_fwer=float((np.sum(np.abs(n).max(1) >= abs(o[kAC]))+1)/(NP+1)), rank=int((np.abs(o) > abs(o[kAC])).sum()+1))
med = np.median(eq); t1, t2 = np.percentile(eq, [100/3, 200/3])
put('consensus_splits', dict(kmeans=split_test(hi, ~hi), median=split_test(eq > med, eq < med), tertiles=split_test(eq >= t2, eq <= t1)))
def cont(e):
    z = zs(e); B = np.einsum('n,nkd->kd', z, X - X.mean(0))/N; Ph, Pl = X.mean(0)+B, X.mean(0)-B
    return cosd(Ph[iA], Ph[iC]) - cosd(Pl[iA], Pl[iC])
o = cont(eq); n = np.array([cont(rng.permutation(eq)) for _ in range(NP)])
infl = [(lambda m: (geo(hi & m) - geo(~hi & m))[kAC])(np.arange(N) != i) for i in range(N)]
bsd = []
for _ in range(NP):
    s = rng.integers(0, N, N); h = hi[s]
    if h.sum() > 4 and (~h).sum() > 4: P1, P0 = X[s][h].mean(0), X[s][~h].mean(0); bsd.append(cosd(P1[iA], P1[iC]) - cosd(P0[iA], P0[iC]))
put('consensus_AxC_robustness', dict(continuous_diff=float(o), continuous_p=float((np.sum(np.abs(n) >= abs(o))+1)/(NP+1)),
    loo_range=[float(min(infl)), float(max(infl))], boot_ci=[float(x) for x in np.percentile(bsd, [2.5, 97.5])]))
np.save(os.path.join(OUT, 'consensus_prototypes.npy'), np.stack([gp(hi), gp(~hi), X.mean(0)]))   # 3 x 13 x 199
np.savez(os.path.join(OUT, 'fig_person_level.npz'), eq=eq, typ=TY.mean(1), gran=W.mean(1), conv=conv, acc=acc, hi=hi,
         dz=np.array([t['dz'] for t in TV]), dzlo=np.array([t['dz_lo'] for t in TV]), dzhi=np.array([t['dz_hi'] for t in TV]),
         cons=obs, cons_null=nl.mean(0), cons_null95=np.percentile(nl, 95, axis=0), rel_w=SH.mean(0), rel_b=XH.mean(0))

# ---------------------------------------------------------------- 7. sensitivity
put('sensitivity', dict(min_r_80=float(next(r for r in np.arange(.05, .9, .005) if 1-stats.norm.cdf(1.96-np.arctanh(r)*np.sqrt(N-3)) >= .8)),
    min_d_80_bonf156=1.32, n_perm=NP, seed=SEED))
json.dump(R, open(os.path.join(OUT, 'results.json'), 'w'), indent=1)
print('done', len(R), 'result blocks')
