"""Agreement between the PS-1 LLM judge and reference labels.

results/ps1_label_sheet.csv holds two kinds of reference label, kept separate:
  - `ai_prelabel (1/0)`: labels from a different-family AI rater (Claude). Not human.
  - `human_verified (edit if you disagree)`: filled only by a person who has checked the row.

  python harness/ps1_agreement.py
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, load_jsonl  # noqa: E402


def cohen_kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe), po


def compare(pairs):
    if not pairs:
        return None
    k, po = cohen_kappa([p[0] for p in pairs], [p[1] for p in pairs])
    ref_pos = sum(r for r, _ in pairs)
    judge_pos = sum(j for _, j in pairs)
    tp = sum(r and j for r, j in pairs)
    return {"n": len(pairs), "raw_agreement": round(po, 3),
            "cohen_kappa": None if k is None else round(k, 3),
            "reference_violations": ref_pos, "judge_violations": judge_pos,
            "judge_recall": round(tp / max(1, ref_pos), 3),
            "judge_precision": round(tp / max(1, judge_pos), 3)}


def main():
    judged = {(j["id"], j["model"]): j for j in load_jsonl(ROOT / "results" / "ps1_judged.jsonl")}
    ai, human = [], []
    per_model = {}
    with (ROOT / "results" / "ps1_label_sheet.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            j = judged.get((row["id"], row["model"]))
            if not j or j["violation"] is None:
                continue
            jv = int(j["violation"])
            a = row.get("ai_prelabel (1/0)", "").strip()
            if a in ("0", "1"):
                ai.append((int(a), jv))
                pm = per_model.setdefault(row["model"], {"en": [0, 0], "hinglish": [0, 0], "marathi": [0, 0]})
                pm[row["lang"]][0] += int(a)
                pm[row["lang"]][1] += 1
            h = row.get("human_verified (edit if you disagree)", "").strip()
            if h in ("0", "1"):
                human.append((int(h), jv))
    res = {"judge_vs_ai_prelabels": compare(ai),
           "judge_vs_human": compare(human),
           "ai_prelabel_violation_rate": {m: {k: f"{v}/{n}" for k, (v, n) in d.items()} for m, d in per_model.items()},
           "note": "ai_prelabel = Claude, a different model family; not human validation."}
    (ROOT / "results" / "ps1_agreement.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
