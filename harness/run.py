"""Run a suite (PS-3 or PS-1) against one model and log raw responses.

  python harness/run.py --suite data/ps3_cases.jsonl --backend ollama --model qwen3.5:9b
  python harness/run.py --suite data/ps1_cases.jsonl --backend ollama --model qwen3.5:4b

Output: results/raw/<suite>__<model>.jsonl, one line per case. Resumable: cases
already present in the output file are skipped, so a killed run can be restarted.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, TOOLS, Mock, build_messages, call_with_retry, load_jsonl, make_backend, add_backend_args  # noqa: E402


def slug(s):
    return "".join(ch if ch.isalnum() or ch in "-." else "_" for ch in s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out")
    add_backend_args(ap)
    args = ap.parse_args()

    cases = load_jsonl(args.suite)[: args.limit]
    backend = make_backend(args)
    if isinstance(backend, Mock):
        backend.bind(cases)

    suite = Path(args.suite).stem.replace("_cases", "")
    out = Path(args.out) if args.out else ROOT / "results" / "raw" / f"{suite}__{slug(args.model)}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["id"] for l in out.open(encoding="utf-8")} if out.exists() else set()

    todo = [c for c in cases if c["id"] not in done]
    print(f"{args.model}: {len(todo)} to run ({len(done)} already done) -> {out}")
    t_start = time.time()
    with out.open("a", encoding="utf-8") as fh:
        for i, c in enumerate(todo, 1):
            r = call_with_retry(backend, build_messages(c), TOOLS)
            rec = {"id": c["id"], "model": args.model, "backend": args.backend, **r}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if r.get("thinking"):
                print(f"  WARNING {c['id']}: model emitted thinking tokens — thinking mode is not off")
            if i % 10 == 0 or i == len(todo):
                el = time.time() - t_start
                print(f"  {i}/{len(todo)}  {el/i:.1f}s/case  eta {el/i*(len(todo)-i)/60:.0f} min")


if __name__ == "__main__":
    main()
