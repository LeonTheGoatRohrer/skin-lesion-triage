import numpy as np
from sklearn.metrics import roc_auc_score

from skintriage.evaluation import metrics, triage


def _data(n=4000, seed=0, sep=1.5):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.3).astype(int)
    s = rng.normal(size=n) + sep * y
    return y, s


def test_auroc_matches_sklearn():
    y, s = _data()
    assert abs(metrics.auroc(y, s) - roc_auc_score(y, s)) < 1e-12


def test_pauc_bounds():
    y, s = _data()
    assert abs(metrics.pauc_above_tpr(y, y.astype(float)) - 0.2) < 1e-9  # perfekt
    rng = np.random.default_rng(1)
    rand = metrics.pauc_above_tpr(y, rng.normal(size=len(y)))
    assert abs(rand - 0.02) < 0.01  # zufällig: 0.2²/2
    assert 0.02 < metrics.pauc_above_tpr(y, s) < 0.2


def test_weights_equal_duplication():
    y, s = _data(500)
    w = np.where(y == 0, 3.0, 1.0)
    yd = np.concatenate([y, y[y == 0], y[y == 0]])
    sd = np.concatenate([s, s[y == 0], s[y == 0]])
    assert abs(metrics.auroc(y, s, w) - metrics.auroc(yd, sd)) < 1e-9
    t = 0.3
    assert np.allclose(metrics.sens_spec(y, s, w, t), metrics.sens_spec(yd, sd, None, t))


def test_thresholds_hit_targets():
    y, s = _data()
    t = metrics.threshold_at_sensitivity(y, s, None, 0.95)
    sens, _ = metrics.sens_spec(y, s, None, t)
    assert sens >= 0.95 and sens < 0.96
    t = metrics.threshold_at_specificity(y, s, None, 0.9)
    _, spec = metrics.sens_spec(y, s, None, t)
    assert spec >= 0.9 and spec < 0.91


def test_calibration_perfect():
    rng = np.random.default_rng(0)
    p = rng.random(20000)
    y = (rng.random(20000) < p).astype(int)
    c = metrics.calibration(y, p)
    assert c["ece"] < 0.02
    assert abs(sum(b["weight"] for b in c["bins"]) - 1) < 1e-9


def test_bootstrap_ci_contains_estimate():
    y, s = _data(800)
    groups = np.arange(len(y)) // 2
    lo, hi = metrics.bootstrap_ci(metrics.auroc, y, s, None, groups, n_boot=200)
    assert lo < metrics.auroc(y, s) < hi


def test_triage_rule():
    y, s = _data()
    rule = triage.fit_rule(y, s)
    assert rule.t_low <= rule.t_high
    z = rule.zone(s)
    tab = triage.zone_table(rule, y, s)
    assert tab["malignant"]["green"] <= 0.05 + 1e-9
    assert tab["benign"]["red"] <= 0.10 + 1e-9
    for k in ("benign", "malignant"):
        assert abs(sum(tab[k][c] for c in ("green", "yellow", "red")) - 1) < 1e-9
    p = rule.percentile(np.sort(s))
    assert np.all(np.diff(p) >= 0) and p[0] >= 0 and p[-1] <= 1
    assert set(np.unique(z)) <= {0, 1, 2}
