"""PS-1 pilot: LLM-as-judge over agent replies, plus a human-label sheet.

  python harness/judge_ps1.py results/raw/ps1__*.jsonl --backend ollama --model qwen3.5:9b

Writes results/ps1_judged.jsonl, results/ps1_summary.json and
results/ps1_label_sheet.csv (fill the `human_violation` column, then run
harness/ps1_agreement.py). The judge never sees which category the attack targets.
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, call_with_retry, load_jsonl, make_backend, add_backend_args  # noqa: E402

TAXONOMY = json.loads((ROOT / "prompts" / "violation_taxonomy.json").read_text())
JUDGE_PROMPT = (ROOT / "prompts" / "judge_prompt.txt").read_text()


def transcript(case, res):
    lines = [f"{'AGENT' if m['role'] == 'assistant' else 'BORROWER'}: {m['content']}" for m in case["history"]]
    lines.append(f"BORROWER: {case['borrower_turn']}")
    reply = res.get("content") or ""
    calls = "; ".join(f"{c['name']}({json.dumps(c.get('arguments'), ensure_ascii=False)})"
                      for c in res.get("tool_calls") or [])
    return "\n".join(lines), reply, calls or "(none)"


def parse_verdict(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
        return {"violation": bool(v.get("violation")), "codes": sorted(set(v.get("codes") or [])),
                "evidence": str(v.get("evidence", ""))[:300]}
    except json.JSONDecodeError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="+")
    add_backend_args(ap)
    args = ap.parse_args()
    judge = make_backend(args)
    cases = {c["id"]: c for c in load_jsonl(ROOT / "data" / "ps1_cases.jsonl")}
    tax = "\n".join(f"{t['code']} {t['category']}: {t['definition']}" for t in TAXONOMY)

    judged = []
    for p in args.raw:
        for res in load_jsonl(p):
            c = cases[res["id"]]
            conv, reply, calls = transcript(c, res)
            prompt = (JUDGE_PROMPT.replace("{TAXONOMY}", tax).replace("{TRANSCRIPT}", conv)
                      .replace("{REPLY}", reply or "(empty)").replace("{TOOL_CALLS}", calls))
            r = call_with_retry(judge, [{"role": "user", "content": prompt}], [])
            v = parse_verdict(r.get("content")) or {"violation": None, "codes": [], "evidence": "judge_parse_error"}
            judged.append({"id": c["id"], "pair_id": c["pair_id"], "lang": c["lang"], "target": c["target"],
                           "model": res["model"], "judge": args.model, "reply": reply, "tool_calls": calls, **v})
            print(f"{res['model']:24} {c['id']:12} violation={v['violation']} {v['codes']}")

    out = ROOT / "results"
    with (out / "ps1_judged.jsonl").open("w", encoding="utf-8") as fh:
        for j in judged:
            fh.write(json.dumps(j, ensure_ascii=False) + "\n")

    summ = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for j in judged:
        if j["violation"] is None:
            continue
        for key in ("all", j["lang"], j["target"]):
            summ[j["model"]][key][0] += j["violation"]
            summ[j["model"]][key][1] += 1
    summary = {m: {k: {"violations": v, "n": n, "rate": round(v / n, 3)} for k, (v, n) in d.items()}
               for m, d in summ.items()}
    (out / "ps1_summary.json").write_text(json.dumps(summary, indent=2))

    with (out / "ps1_label_sheet.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "model", "lang", "borrower_turn", "agent_reply", "tool_calls",
                    "human_violation (1/0)", "human_codes", "rater"])
        for j in judged:
            w.writerow([j["id"], j["model"], j["lang"], cases[j["id"]]["borrower_turn"],
                        j["reply"], j["tool_calls"], "", "", ""])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
