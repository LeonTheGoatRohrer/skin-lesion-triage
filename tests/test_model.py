import numpy as np
import torch

from skintriage import labels
from skintriage.evaluation.ood import calibrate_threshold, fit_ood
from skintriage.models.losses import set_nll
from skintriage.models.net import TriageNet, malignant_logit
from skintriage.training.augment import AugConfig, augment


def test_set_nll_equals_cross_entropy_for_single_labels():
    torch.manual_seed(0)
    logits = torch.randn(16, labels.N_GROUPS)
    y = torch.randint(0, labels.N_GROUPS, (16,))
    mask = torch.nn.functional.one_hot(y, labels.N_GROUPS).bool()
    ce = torch.nn.functional.cross_entropy(logits, y)
    assert torch.allclose(set_nll(logits, mask), ce, atol=1e-6)


def test_set_nll_full_set_is_zero_and_rejects_empty():
    logits = torch.randn(4, labels.N_GROUPS)
    assert set_nll(logits, torch.ones(4, labels.N_GROUPS, dtype=torch.bool)).abs() < 1e-6
    bad = torch.zeros(4, labels.N_GROUPS, dtype=torch.bool)
    try:
        set_nll(logits, bad)
    except ValueError:
        pass
    else:
        raise AssertionError("leere Maske muss Fehler werfen")


def test_malignant_logit_matches_probabilities():
    logits = torch.randn(8, labels.N_GROUPS)
    p = torch.softmax(logits, 1)
    pm = p[:, list(labels.MALIGNANT)].sum(1)
    assert torch.allclose(torch.sigmoid(malignant_logit(logits)), pm, atol=1e-6)


def test_net_forward_shapes():
    net = TriageNet("mobilenetv3_large_100", pretrained=False).eval()
    with torch.no_grad():
        logits, emb = net(torch.rand(2, 3, 128, 128))
    assert logits.shape == (2, labels.N_GROUPS)
    assert emb.shape == (2, net.feat_dim)


def test_augment_shapes_and_range():
    g = torch.Generator().manual_seed(0)
    x = torch.randint(0, 256, (6, 160, 160, 3), dtype=torch.uint8)
    out = augment(x, 128, AugConfig(), g)
    assert out.shape == (6, 3, 128, 128)
    assert out.min() >= 0 and out.max() <= 1
    g2 = torch.Generator().manual_seed(0)
    assert torch.equal(out, augment(x, 128, AugConfig(), g2))  # reproduzierbar


def test_ood_flags_outliers():
    rng = np.random.default_rng(0)
    basis = rng.normal(size=(8, 64))
    train = rng.normal(size=(2000, 8)) @ basis + 0.05 * rng.normal(size=(2000, 64))
    val = rng.normal(size=(500, 8)) @ basis + 0.05 * rng.normal(size=(500, 64))
    m = calibrate_threshold(fit_ood(train, k=8), val, 0.99)
    assert 0.5 < np.median(m.score(val)) < 2.0
    outlier = rng.normal(size=(20, 64)) * 3  # Richtungen, die im Training nie vorkamen
    assert (m.score(outlier) > m.threshold).mean() > 0.9
