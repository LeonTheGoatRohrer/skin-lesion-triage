"""Kommandozeile: ``python -m skintriage.cli <befehl>`` (oder ``skintriage <befehl>``)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skintriage import config


def cmd_download(args) -> int:
    from skintriage.data import download as dl

    try:
        print("Bulk-Dateien (ISIC-S3):")
        dl.download_bulk()
        print("Einzelbilder (klinische Nahaufnahmen):")
        dl.download_single_images()
        print("SCIN (Realitätscheck):")
        dl.download_scin()
    except dl.DataUnavailableError as exc:
        print(f"FEHLER: Daten nicht erreichbar ({exc}).\n"
              "isic-archive.s3.amazonaws.com bzw. storage.googleapis.com müssen erreichbar sein.",
              file=sys.stderr)
        return 2
    return 0


def cmd_preprocess(args) -> int:
    from skintriage.data import catalog, preprocess

    cat = preprocess.preprocess_all()
    print(catalog.summarize(cat).to_string())
    preprocess.preprocess_scin()
    return 0


def cmd_train(args) -> int:
    from skintriage.training.train import TrainConfig, train

    cfg = TrainConfig.from_json(args.config) if args.config else TrainConfig()
    for kv in args.set or []:
        k, v = kv.split("=", 1)
        cfg = cfg.override(k, v)
    train(cfg, out_dir=Path(args.out))
    return 0


def cmd_evaluate(args) -> int:
    from skintriage.evaluation.run import evaluate_run

    res = evaluate_run(Path(args.run), splits=args.splits.split(","))
    print(json.dumps(res["summary"], indent=2, ensure_ascii=False))
    return 0


def cmd_export(args) -> int:
    from skintriage.export.web_export import export_all

    export_all(Path(args.run), web_public=Path(args.web), preliminary=args.preliminary)
    return 0


def cmd_predict(args) -> int:
    from skintriage.export.predict import predict_files

    for line in predict_files(Path(args.model_dir), [Path(p) for p in args.images]):
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="skintriage", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("download", help="ISIC- und SCIN-Daten laden (~3 GB)").set_defaults(fn=cmd_download)
    sub.add_parser("preprocess", help="Katalog + Splits + Memmap bauen").set_defaults(fn=cmd_preprocess)

    t = sub.add_parser("train", help="Modell trainieren")
    t.add_argument("--config", help="JSON mit TrainConfig-Feldern")
    t.add_argument("--set", nargs="*", help="Einzelwerte überschreiben, z. B. epochs=3")
    t.add_argument("--out", default=str(config.ARTIFACTS_DIR / "runs" / "default"))
    t.set_defaults(fn=cmd_train)

    e = sub.add_parser("evaluate", help="Lauf auswerten")
    e.add_argument("--run", required=True)
    e.add_argument("--splits", default="val")
    e.set_defaults(fn=cmd_evaluate)

    x = sub.add_parser("export", help="ONNX + Web-Daten exportieren")
    x.add_argument("--run", required=True)
    x.add_argument("--web", default=str(config.WEB_PUBLIC))
    x.add_argument("--preliminary", action="store_true", help="nur Val-Auswertung nutzen (Entwicklung)")
    x.set_defaults(fn=cmd_export)

    pr = sub.add_parser("predict", help="Fotos mit dem exportierten Modell bewerten")
    pr.add_argument("images", nargs="+")
    pr.add_argument("--model-dir", default=str(config.WEB_PUBLIC))
    pr.set_defaults(fn=cmd_predict)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
