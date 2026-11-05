import numpy as np
import pandas as pd

from skintriage.training.data import ShardedImages, StratifiedSampler


def test_sharded_images_index_like_one_array():
    a = np.arange(5 * 2 * 2 * 3, dtype=np.uint8).reshape(5, 2, 2, 3)
    b = (np.arange(3 * 2 * 2 * 3, dtype=np.uint8) + 100).reshape(3, 2, 2, 3)
    s = ShardedImages([a, b])
    full = np.concatenate([a, b])
    rows = np.array([7, 0, 5, 4, 6])
    assert s.shape == full.shape
    assert np.array_equal(s[rows], full[rows])
    assert np.array_equal(s[np.int64(6)], full[6])


def _cat():
    # 100 BCC, 10 Melanome (bösartig) und 110 Nävi in einer Domäne
    g = np.r_[np.full(100, 1), np.full(10, 0), np.full(110, 4)]
    return pd.DataFrame({"domain": "clinical", "binary": (g < 4).astype(int), "group_label": g})


def test_sampler_respects_domain_fractions():
    cat = _cat()
    s = StratifiedSampler(cat, np.arange(len(cat)), {"clinical": 1.0}, {"clinical": 0.5}, seed=0)
    draw = s.epoch(20000)
    assert abs(cat.binary.to_numpy()[draw].mean() - 0.5) < 0.02


def test_group_balance_upweights_rare_groups():
    cat = _cat()
    idx = np.arange(len(cat))
    plain = StratifiedSampler(cat, idx, {"clinical": 1.0}, {"clinical": 0.5}, seed=0).epoch(20000)
    bal = StratifiedSampler(cat, idx, {"clinical": 1.0}, {"clinical": 0.5}, seed=0, group_balance=1.0).epoch(20000)
    mel_plain = (cat.group_label.to_numpy()[plain] == 0).mean()
    mel_bal = (cat.group_label.to_numpy()[bal] == 0).mean()
    assert abs(mel_plain - 0.5 * 10 / 110) < 0.01   # proportional
    assert abs(mel_bal - 0.25) < 0.02               # Melanom = BCC innerhalb der Bösartigen
