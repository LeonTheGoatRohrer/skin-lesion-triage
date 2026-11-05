from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from skintriage import config, labels
from skintriage.data import catalog


def test_union_find_links_patient_and_lesion():
    # Bild 0 und 1: gleicher Patient; Bild 1 und 2: gleiche Läsion -> alle drei eine Gruppe
    pid = pd.Series(["P1", "P1", None, "P2", None])
    lid = pd.Series([None, "L1", "L1", None, None])
    g = catalog.assign_groups(pid, lid)
    assert g[0] == g[1] == g[2]
    assert len({g[0], g[3], g[4]}) == 3


def test_split_groups_never_splits_a_group():
    rng = np.random.default_rng(1)
    n = 3000
    df = pd.DataFrame({
        "group": rng.integers(0, 600, n),
        "domain": rng.choice(["clinical", "tbp"], n),
        "binary": rng.choice([0, 1], n, p=[0.8, 0.2]),
    })
    df["split"] = catalog.split_groups(df, seed=3)
    assert (df.groupby("group").split.nunique() == 1).all()
    frac = df.split.value_counts(normalize=True)
    assert 0.08 < frac["test"] < 0.25 and 0.08 < frac["val"] < 0.25


CAT = config.PROCESSED_DIR / "catalog.parquet"


@pytest.mark.skipif(not CAT.exists(), reason="Daten nicht vorverarbeitet")
def test_real_catalog_has_no_leakage():
    cat = pd.read_parquet(CAT)
    # keine Gruppe (Patient/Läsion) in zwei Splits
    assert (cat.groupby("group").split.nunique() == 1).all()
    # PAD-UFES-20 ausschließlich extern, alles andere nie extern
    assert (cat[cat.source == "pad_ufes_20"].split == "external").all()
    assert (cat[cat.source != "pad_ufes_20"].split != "external").all()
    # Kamerafoto und Dermoskopie derselben MILK10k-Läsion im selben Split
    milk = cat[cat.source == "milk10k"]
    assert (milk.groupby("lesion_id").split.nunique() == 1).all()
    # unklare Labels sind nicht im Katalog
    assert (cat.binary != labels.BIN_UNKNOWN).all()
    # Gewichte der SLICE-3D-Stichprobe: nur Gutartige > 1
    assert (cat[(cat.weight > 1)].binary == 0).all()
    assert Path(cat.file.iloc[0]).name
