"""Score PS-3 raw results. Metric definitions: METRICS.md (fixed before any model was run).

  python harness/score_ps3.py results/raw/ps3__*.jsonl

Writes results/ps3_scored.jsonl (per case), results/ps3_summary.json and results/ps3_report.md.
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, TOOLS, TOOL_NAMES, load_jsonl  # noqa: E402

SCHEMA = {t["name"]: t["parameters"] for t in TOOLS}
LEAK_RE = re.compile(r"\b(" + "|".join(TOOL_NAMES) + r")\b")


# ---------------------------------------------------------------- validation
def validate(call):
    """Return a list of schema violations for one tool call (empty = well-formed)."""
    if call["name"] not in SCHEMA:
        return [f"unknown_tool:{call['name']}"]
    if not call["parse_ok"]:
        return ["unparseable_json"]
    sch, args, errs = SCHEMA[call["name"]], call["arguments"], []
    for req in sch.get("required", []):
        if req not in args or args[req] in (None, ""):
            errs.append(f"missing:{req}")
    for k, v in args.items():
        spec = sch["properties"].get(k)
        if spec is None:
            errs.append(f"unknown_arg:{k}")
            continue
        if spec["type"] == "number" and (isinstance(v, bool) or not isinstance(v, (int, float))):
            errs.append(f"type:{k}")
        if spec["type"] == "string" and not isinstance(v, str):
            errs.append(f"type:{k}")
        if "enum" in spec and v not in spec["enum"]:
            errs.append(f"enum:{k}")
        if spec.get("format") == "date" and isinstance(v, str):
            try:
                date.fromisoformat(v)
            except ValueError:
                errs.append(f"date_format:{k}")
    return errs


def value_matches(field, got, allowed):
    """Lenient value comparison, used for argument accuracy (validity is scored separately)."""
    if got is None:
        return False
    for a in allowed:
        if isinstance(a, (int, float)):
            try:
                if abs(float(str(got).replace(",", "").replace("₹", "")) - a) < 0.5:
                    return True
            except ValueError:
                pass
        elif field.endswith("date"):
            if str(got)[:10] == a:
                return True
        elif str(got).strip().lower() == str(a).lower():
            return True
    return False


# ---------------------------------------------------------------- per case
def judge_outcome(outcome, calls):
    """Score calls against one acceptable outcome. Returns a dict of flags."""
    action = [c for c in calls if c["name"] != "log_disposition"]
    if outcome is None:
        ok = not calls
        return {"tool_ok": ok, "args_ok": ok, "matched": None,
                "kind": "correct" if ok else "spurious", "arg_errors": []}
    want = outcome["tool"]
    if want == "log_disposition":
        cands = [c for c in calls if c["name"] == "log_disposition"]
        tool_ok = bool(cands) and not action
    else:
        cands = [c for c in action if c["name"] == want]
        tool_ok = bool(cands)
    if not tool_ok:
        kind = "missed" if not calls or (want != "log_disposition" and not action) else "wrong_tool"
        return {"tool_ok": False, "args_ok": False, "matched": None, "kind": kind, "arg_errors": []}
    best = None
    for c in cands:
        a = c["arguments"] or {}
        errs = [f for f, allowed in outcome["args"].items() if not value_matches(f, a.get(f), allowed)]
        if best is None or len(errs) < len(best[1]):
            best = (c, errs)
    return {"tool_ok": True, "args_ok": not best[1], "matched": best[0], "kind": "correct",
            "arg_errors": best[1]}


def score_case(case, res):
    calls = res.get("tool_calls") or []
    malformed = {i: validate(c) for i, c in enumerate(calls)}
    best = None
    for outcome in case["accept"]:
        j = judge_outcome(outcome, calls)
        if j["matched"] is not None:
            j["malformed_matched"] = validate(j["matched"])
        else:
            j["malformed_matched"] = []
        j["full_ok"] = j["tool_ok"] and j["args_ok"] and not j["malformed_matched"]
        rank = (j["full_ok"], j["tool_ok"], j["args_ok"])
        if best is None or rank > best[0]:
            best = (rank, j, outcome)
    _, j, outcome = best
    primary = case["accept"][0]
    leaked = not calls and bool(LEAK_RE.search(res.get("content") or ""))

    tags = []
    if res.get("error"):
        tags.append("backend_error")
    elif j["kind"] == "missed":
        tags.append(f"missed:{primary['tool'] if primary else '-'}" + (":leaked_as_text" if leaked else ""))
    elif j["kind"] == "wrong_tool":
        got = ",".join(sorted({c['name'] for c in calls}))
        tags.append(f"wrong_tool:{primary['tool'] if primary else 'none'}->{got}")
    elif j["kind"] == "spurious":
        tags.append("spurious:" + ",".join(sorted({c['name'] for c in calls})))
    tags += [f"arg:{f}" for f in j["arg_errors"]]
    tags += [f"malformed:{e}" for errs in malformed.values() for e in errs]

    conf = None
    if case.get("gold_confidence") and j["matched"] and j["matched"]["name"] == "capture_ptp":
        given = (j["matched"]["arguments"] or {}).get("confidence")
        conf = None if given is None else given == case["gold_confidence"]

    return {"id": case["id"], "pair_id": case["pair_id"], "lang": case["lang"], "set": case["set"],
            "intent": case["intent"], "model": res["model"], "expects_tool": primary is not None,
            "none_acceptable": None in case["accept"],
            "kind": j["kind"], "tool_ok": j["tool_ok"], "args_ok": j["args_ok"], "full_ok": j["full_ok"],
            "any_call": bool(calls), "any_malformed": any(malformed.values()),
            "extra_action_calls": max(0, len([c for c in calls if c["name"] != "log_disposition"]) - 1),
            "leaked_text_call": leaked, "confidence_ok": conf, "error": res.get("error"),
            "tags": tags, "calls": [{"name": c["name"], "arguments": c["arguments"]} for c in calls],
            "content": (res.get("content") or "")[:400], "latency_s": res.get("latency_s")}


# ---------------------------------------------------------------- aggregate
def rate(num, den):
    return None if den == 0 else round(num / den, 4)


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def aggregate(rows):
    n = len(rows)
    exp = [r for r in rows if r["expects_tool"] and not r["none_acceptable"]]
    none_only = [r for r in rows if not r["expects_tool"]]
    called = [r for r in rows if r["any_call"]]
    tool_ok = [r for r in rows if r["tool_ok"] and r["expects_tool"]]
    conf = [r for r in rows if r["confidence_ok"] is not None]
    k = sum(r["full_ok"] for r in rows)
    return {
        "n": n,
        "full_correct": rate(k, n), "full_correct_ci95": wilson(k, n),
        "correct_tool": rate(sum(r["tool_ok"] for r in rows), n),
        "arg_accuracy_given_tool": rate(sum(r["args_ok"] for r in tool_ok), len(tool_ok)),
        "missed_call_rate": rate(sum(r["kind"] == "missed" for r in exp), len(exp)),
        "wrong_tool_rate": rate(sum(r["kind"] == "wrong_tool" for r in exp), len(exp)),
        "spurious_call_rate": rate(sum(r["kind"] == "spurious" for r in none_only), len(none_only)),
        "malformed_rate": rate(sum(r["any_malformed"] for r in called), len(called)),
        "leaked_text_call_rate": rate(sum(r["leaked_text_call"] for r in rows), n),
        "confidence_agreement": rate(sum(r["confidence_ok"] for r in conf), len(conf)),
        "backend_errors": sum(bool(r["error"]) for r in rows),
    }


def mcnemar(rows_en, rows_hi):
    """Paired comparison on core pairs: exact two-sided McNemar test on full_correct."""
    hi = {r["pair_id"]: r for r in rows_hi}
    b = c = 0
    for r in rows_en:
        h = hi.get(r["pair_id"])
        if h is None:
            continue
        b += r["full_ok"] and not h["full_ok"]
        c += h["full_ok"] and not r["full_ok"]
    m = b + c
    p = 1.0 if m == 0 else min(1.0, 2 * sum(math.comb(m, i) for i in range(min(b, c) + 1)) / 2 ** m)
    return {"en_only_correct": b, "hinglish_only_correct": c, "p_value": round(p, 4)}


def main(paths):
    cases = {c["id"]: c for c in load_jsonl(ROOT / "data" / "ps3_cases.jsonl")}
    scored = []
    for p in paths:
        for res in load_jsonl(p):
            if res["id"] in cases:
                scored.append(score_case(cases[res["id"]], res))
    out_dir = ROOT / "results"
    with (out_dir / "ps3_scored.jsonl").open("w", encoding="utf-8") as fh:
        for r in scored:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_model = defaultdict(list)
    for r in scored:
        by_model[r["model"]].append(r)

    summary = {}
    for model, rows in by_model.items():
        core_en = [r for r in rows if r["set"] == "core" and r["lang"] == "en"]
        core_hi = [r for r in rows if r["set"] == "core" and r["lang"] == "hinglish"]
        s = {"all": aggregate(rows),
             "core_en": aggregate(core_en), "core_hinglish": aggregate(core_hi),
             "marathi": aggregate([r for r in rows if r["set"] == "marathi"]),
             "ambiguous": aggregate([r for r in rows if r["set"] == "ambiguous"])}
        amb = [r for r in rows if r["set"] == "ambiguous"]
        s["ambiguous"]["over_fire_rate"] = rate(sum(r["any_call"] and not r["full_ok"] and r["none_acceptable"]
                                                    for r in amb), sum(r["none_acceptable"] for r in amb))
        s["ambiguous"]["under_fire_rate"] = rate(sum(not r["any_call"] for r in amb if not r["none_acceptable"]),
                                                 sum(not r["none_acceptable"] for r in amb))
        if core_en and core_hi:
            s["delta_en_minus_hinglish"] = {
                k: (None if s["core_en"][k] is None or s["core_hinglish"][k] is None
                    else round(s["core_en"][k] - s["core_hinglish"][k], 4))
                for k in ("full_correct", "correct_tool", "arg_accuracy_given_tool", "missed_call_rate")}
            s["delta_en_minus_hinglish"]["mcnemar_full_correct"] = mcnemar(core_en, core_hi)
        s["by_intent"] = {}
        for intent in sorted({r["intent"] for r in rows}):
            for lang in ("en", "hinglish", "marathi"):
                sub = [r for r in rows if r["intent"] == intent and r["lang"] == lang and r["set"] != "ambiguous"]
                if sub:
                    s["by_intent"][f"{intent}/{lang}"] = rate(sum(r["full_ok"] for r in sub), len(sub))
        s["error_tags"] = Counter(t for r in rows for t in r["tags"]).most_common()
        summary[model] = s

    (out_dir / "ps3_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    (out_dir / "ps3_report.md").write_text(render(summary))
    print(render(summary))


def pct(x):
    return "—" if x is None else f"{100 * x:.1f}%"


def render(summary):
    L = ["# PS-3 results", "", "Generated by `harness/score_ps3.py`. Definitions in `METRICS.md`.", "",
         "## Headline: English vs Hinglish on 80 paired core cases", "",
         "| Model | Full-correct EN | Full-correct Hinglish | Δ (EN − HI) | EN-only / HI-only correct | McNemar p |",
         "|---|---|---|---|---|---|"]
    for m, s in summary.items():
        if "delta_en_minus_hinglish" not in s:
            continue
        d = s["delta_en_minus_hinglish"]
        mc = d["mcnemar_full_correct"]
        delta = "—" if d["full_correct"] is None else "%+.1f pts" % (100 * d["full_correct"])
        L.append(f"| {m} | {pct(s['core_en']['full_correct'])} | {pct(s['core_hinglish']['full_correct'])} | "
                 f"{delta} | "
                 f"{mc['en_only_correct']} / {mc['hinglish_only_correct']} | {mc['p_value']} |")
    cols = [("full_correct", "Full-correct"), ("correct_tool", "Correct tool"),
            ("arg_accuracy_given_tool", "Arg acc. (given tool)"), ("missed_call_rate", "Missed"),
            ("wrong_tool_rate", "Wrong tool"), ("spurious_call_rate", "Spurious"),
            ("malformed_rate", "Malformed"), ("leaked_text_call_rate", "Leaked as text")]
    for key, title in [("core_en", "Core — English (n=80)"), ("core_hinglish", "Core — Hinglish (n=80)"),
                       ("marathi", "Marathi (n=20)"), ("ambiguous", "Ambiguous Hinglish (n=20)"),
                       ("all", "All 200 cases")]:
        L += ["", f"## {title}", "", "| Model | " + " | ".join(t for _, t in cols) + " |",
              "|---|" + "---|" * len(cols)]
        for m, s in summary.items():
            L.append(f"| {m} | " + " | ".join(pct(s[key].get(k)) for k, _ in cols) + " |")
    L += ["", "## Ambiguous set: over- and under-firing", "", "| Model | Over-fire | Under-fire |", "|---|---|---|"]
    for m, s in summary.items():
        L.append(f"| {m} | {pct(s['ambiguous'].get('over_fire_rate'))} | {pct(s['ambiguous'].get('under_fire_rate'))} |")
    L += ["", "## Most frequent error tags", ""]
    for m, s in summary.items():
        L.append(f"**{m}**: " + ", ".join(f"`{t}` ×{n}" for t, n in s["error_tags"][:12]) or "none")
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: score_ps3.py results/raw/ps3__*.jsonl")
    main(sys.argv[1:])
