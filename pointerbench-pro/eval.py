#!/usr/bin/env python3
"""Pointerbench-Pro official scorer.

Metric: **point-in-bbox accuracy** (the ScreenSpot standard). A prediction is
correct when the predicted click point falls inside the target's ground-truth
bounding box. Reports overall accuracy plus per-element-type, per-app-category,
per-platform, and per-app breakdowns. Pure standard library, no dependencies.

Ground truth is read from `data/test/metadata.jsonl` (shipped with the repo).

Predictions file: JSONL or JSON list, one object per example, e.g.
    {"id": "pbp_0001", "point": [612, 388]}
Accepted point keys: "point" / "pred" / "coordinate", or flat "x" and "y".
Coordinates are absolute pixels on the 1024x768 image.

Usage:
    python eval.py --show-system-prompt
    python eval.py --predictions preds.jsonl
    python eval.py --predictions preds.jsonl --json report.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GT_PATH = ROOT / "data" / "test" / "metadata.jsonl"

AXES = ("element_type", "app_category", "platform", "app")

DEFAULT_SYSTEM_PROMPT = (
    "You are evaluating Pointerbench, a GUI grounding benchmark. "
    "You will receive one 1024x768 screenshot and one task instruction. "
    "Use absolute pixel coordinates with origin at the top-left of the image. "
    "Do not return normalized coordinates. Do not crop or resize the coordinate frame. "
    "For point tasks, return JSON like {\"point\": [x, y]}. "
    "For bounding-box tasks, return JSON like {\"bbox\": [x0, y0, x1, y1]}."
)


def _load_jsonl(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text[0] == "[":                       # tolerate a JSON array too
        return json.loads(text)
    return [json.loads(ln) for ln in text.splitlines() if ln.strip()]


def _point(rec: dict) -> tuple[float, float] | None:
    for key in ("point", "pred", "coordinate", "prediction"):
        v = rec.get(key)
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            return float(v[0]), float(v[1])
    if "x" in rec and "y" in rec:
        return float(rec["x"]), float(rec["y"])
    return None


def _in_bbox(pt: tuple[float, float], bbox: list[int]) -> bool:
    x0, y0, x1, y1 = bbox
    return min(x0, x1) <= pt[0] <= max(x0, x1) and min(y0, y1) <= pt[1] <= max(y0, y1)


def evaluate(gt: list[dict], preds: dict[str, dict]) -> dict:
    by = {axis: defaultdict(lambda: [0, 0]) for axis in AXES}
    hits = missing = 0
    for ex in gt:
        pred = preds.get(ex["id"])
        pt = _point(pred) if pred else None
        if pt is None:
            missing += 1
            ok = False
        else:
            ok = _in_bbox(pt, ex["bbox"])
        hits += ok
        for axis in AXES:
            cell = by[axis][ex.get(axis, "?")]
            cell[0] += ok
            cell[1] += 1
    n = len(gt)

    def table(axis: str) -> dict:
        return {k: {"acc": round(v[0] / v[1], 4), "n": v[1]}
                for k, v in sorted(by[axis].items())}

    report = {
        "n": n,
        "accuracy": round(hits / n, 4) if n else 0.0,
        "hits": hits,
        "missing_predictions": missing,
    }
    for axis in AXES:
        report[f"by_{axis}"] = table(axis)
    return report


def _print(report: dict) -> None:
    print(f"\nPointerbench-Pro: {report['n']} examples")
    print("=" * 44)
    print(f"Accuracy: {report['accuracy'] * 100:5.2f}%   "
          f"({report['hits']}/{report['n']})")
    if report["missing_predictions"]:
        print(f"  ! {report['missing_predictions']} examples had no prediction "
              f"(counted as wrong)")
    titles = {"element_type": "By target type", "app_category": "By app category",
              "platform": "By platform", "app": "By app"}
    for axis in AXES:
        rows = report[f"by_{axis}"]
        if axis == "app":                     # too many apps to print
            continue
        print(f"\n{titles[axis]}:")
        for k, v in rows.items():
            print(f"  {k:24s} {v['acc'] * 100:5.2f}%   (n={v['n']})")
    print("\n(per-app breakdown is in the --json report)\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show-system-prompt", action="store_true",
                    help="print the recommended inference system prompt and exit")
    ap.add_argument("--predictions", type=Path,
                    help="JSONL/JSON predictions: {id, point:[x,y]} per example")
    ap.add_argument("--gt", type=Path, default=GT_PATH,
                    help=f"ground-truth metadata (default: {GT_PATH})")
    ap.add_argument("--json", type=Path, default=None,
                    help="also write the full report to this JSON path")
    args = ap.parse_args()

    if args.show_system_prompt:
        print(DEFAULT_SYSTEM_PROMPT)
        return
    if args.predictions is None:
        ap.error("--predictions is required unless --show-system-prompt is used")

    gt = _load_jsonl(args.gt)
    preds = {r["id"]: r for r in _load_jsonl(args.predictions) if "id" in r}
    report = evaluate(gt, preds)
    _print(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"report -> {args.json}")


if __name__ == "__main__":
    main()
