#!/usr/bin/env python3
"""Pointerbench-Text official scorer.

Point-answer rows use point-in-bbox accuracy. Bbox-answer rows use an
asymmetric overlap rule: a hit requires the ground truth to be almost fully
covered (coverage >= 0.90) and the prediction to stay reasonably tight around
it (precision >= 0.70). This penalises predictions that cut off part of the
target far more than predictions that wrap it with some margin.
Reports overall accuracy plus per-answer-type, per-data-type,
per-category, per-surface, per-language, and per-difficulty breakdowns. Pure
standard library, no dependencies.

Ground truth is read from `data/test/metadata.jsonl` (shipped with the repo).

Predictions file: JSONL or JSON list, one object per example, e.g.
    {"id": "pbt_0001", "point": [612, 388]}
    {"id": "pbt_0002", "bbox": [193, 643, 807, 688]}
Accepted point keys: "point" / "pred" / "coordinate", or flat "x" and "y".
Accepted bbox keys: "bbox" / "box" / "pred" / "prediction", or flat
"x0", "y0", "x1", "y1".
Coordinates are absolute pixels on the 1024x768 image.

Usage:
    python eval.py --show-system-prompt
    python eval.py --predictions preds.jsonl
    python eval.py --predictions preds.jsonl --json report.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GT_PATH = ROOT / "data" / "test" / "metadata.jsonl"

AXES = ("answer_type", "data_type", "category", "surface", "language", "difficulty")

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


def _numbers(value) -> list[float]:
    if isinstance(value, str):
        return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", value)]
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value if isinstance(x, (int, float))]
    return []


def _bbox(rec: dict) -> list[float] | None:
    for key in ("bbox", "box", "pred", "prediction"):
        nums = _numbers(rec.get(key))
        if len(nums) >= 4:
            return _norm_bbox(nums[:4])
    if all(k in rec for k in ("x0", "y0", "x1", "y1")):
        return _norm_bbox([rec["x0"], rec["y0"], rec["x1"], rec["y1"]])
    nums = _numbers(rec.get("text") or rec.get("raw") or rec.get("answer"))
    if len(nums) >= 4:
        return _norm_bbox(nums[:4])
    return None


def _norm_bbox(bbox: list[float]) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def _in_bbox(pt: tuple[float, float], bbox: list[int]) -> bool:
    x0, y0, x1, y1 = bbox
    return min(x0, x1) <= pt[0] <= max(x0, x1) and min(y0, y1) <= pt[1] <= max(y0, y1)


# Asymmetric bbox rule. Plain IoU treats a box that *cuts off* part of the
# target the same as one that simply overshoots it. For grounding we care far
# more about coverage: a prediction that misses part of the ground truth is the
# worst failure, while a prediction that wraps the target with some margin is
# fine. So a hit requires (a) the GT is almost fully covered and (b) the
# prediction does not balloon far past it.
COVERAGE_MIN = 0.90    # share of GT area that must be inside the prediction
PRECISION_MIN = 0.70   # share of prediction area that must be inside the GT


def _overlap(a: list[float], b: list[int]) -> tuple[float, float, float]:
    """Return (iou, coverage, precision) where coverage = inter/GT and
    precision = inter/pred."""
    ax0, ay0, ax1, ay1 = _norm_bbox(a)
    bx0, by0, bx1, by1 = _norm_bbox([float(v) for v in b])
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    pred_area = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    gt_area = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union = pred_area + gt_area - inter
    iou = inter / union if union else 0.0
    coverage = inter / gt_area if gt_area else 0.0
    precision = inter / pred_area if pred_area else 0.0
    return iou, coverage, precision


def _bbox_hit(pred: list[float], gt: list[int], rule: dict) -> bool:
    _, coverage, precision = _overlap(pred, gt)
    return (coverage >= float(rule.get("min_coverage", COVERAGE_MIN))
            and precision >= float(rule.get("min_precision", PRECISION_MIN)))


def evaluate(gt: list[dict], preds: dict[str, dict]) -> dict:
    by = {axis: defaultdict(lambda: [0, 0]) for axis in AXES}
    hits = missing = 0
    for ex in gt:
        pred = preds.get(ex["id"])
        rule = ex.get("eval") or {}
        answer_type = ex.get("answer_type") or ("bbox" if rule.get("type") == "iou" else "point")
        ex["answer_type"] = answer_type
        if not pred:
            missing += 1
            ok = False
        elif answer_type == "bbox":
            box = _bbox(pred)
            if box is None:
                missing += 1
                ok = False
            else:
                ok = _bbox_hit(box, ex["bbox"], rule)
        else:
            pt = _point(pred)
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
    print(f"\nPointerbench-Text: {report['n']} examples")
    print("=" * 44)
    print(f"Accuracy: {report['accuracy'] * 100:5.2f}%   "
          f"({report['hits']}/{report['n']})")
    if report["missing_predictions"]:
        print(f"  ! {report['missing_predictions']} examples had no prediction "
              f"(counted as wrong)")
    titles = {"answer_type": "By answer type", "data_type": "By data type",
              "category": "By category", "surface": "By surface",
              "language": "By language", "difficulty": "By difficulty"}
    for axis in AXES:
        rows = report[f"by_{axis}"]
        if axis == "surface" and len(rows) > 20:
            continue                          # too many surfaces to print
        print(f"\n{titles[axis]}:")
        for k, v in rows.items():
            print(f"  {k:18s} {v['acc'] * 100:5.2f}%   (n={v['n']})")
    print()


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
