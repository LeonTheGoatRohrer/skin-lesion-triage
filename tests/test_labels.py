import numpy as np
import pytest

from skintriage import labels


@pytest.mark.parametrize("d1,d3,group", [
    ("Malignant", "Melanoma Invasive", 0),
    ("Malignant", "Melanoma in situ", 0),
    ("Malignant", "Basal cell carcinoma", 1),
    ("Malignant", "Squamous cell carcinoma in situ", 2),
    ("Malignant", "Keratoacanthoma", 2),
    ("Indeterminate", "Solar or actinic keratosis", 3),
    ("Benign", "Nevus", 4),
    ("Benign", "Seborrheic keratosis", 5),
    ("Benign", "Solar lentigo", 5),
    ("Benign", "Dermatofibroma", 6),
    ("Benign", "Hemangioma", 6),
])
def test_group_mapping(d1, d3, group):
    assert labels.group_from_diagnosis(d1, d3) == group


def test_coarse_labels_become_sets():
    m = labels.label_mask("Benign", None)
    assert m.tolist() == [False, False, False, False, True, True, True]
    m = labels.label_mask("Malignant", float("nan"))
    assert m.tolist() == [True, True, True, False, False, False, False]
    # Merkelzellkarzinom o. Ä.: bösartig, aber keine der drei Gruppen -> Menge aller bösartigen
    assert labels.label_mask("Malignant", "Merkel cell carcinoma")[:3].all()


def test_indeterminate_without_ak_is_not_trainable():
    assert labels.label_mask("Indeterminate", "Atypical melanocytic neoplasm") is None
    assert labels.binary_label("Indeterminate", "Atypical melanocytic neoplasm") == labels.BIN_UNKNOWN
    assert labels.label_mask(None, None) is None


def test_binary_labels():
    assert labels.binary_label("Malignant", "Basal cell carcinoma") == labels.BIN_MALIGNANT
    assert labels.binary_label("Benign", "Nevus") == labels.BIN_BENIGN
    assert labels.binary_label("Indeterminate", "Solar or actinic keratosis") == labels.BIN_PRECURSOR


def test_mask_bits_roundtrip():
    rng = np.random.default_rng(0)
    for _ in range(20):
        m = rng.random(labels.N_GROUPS) > 0.5
        assert (labels.bits_to_mask(labels.mask_to_bits(m)) == m).all()
