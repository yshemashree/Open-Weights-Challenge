#!/usr/bin/env bash
# Reproduce every Track 1 run. Needs Ollama running locally (ollama serve / the app).
# Optional hosted baseline: set BASELINE_BACKEND (openai|anthropic), BASELINE_MODEL,
# and the key (OPENAI_API_KEY / ANTHROPIC_API_KEY). BASELINE_BASE_URL is optional.
set -euo pipefail
cd "$(dirname "$0")"

MODELS=("qwen3.5:4b" "qwen3.5:9b")
JUDGE_MODEL="${JUDGE_MODEL:-qwen3.5:9b}"

python3 data/build_ps3_cases.py
python3 data/build_ps1_cases.py

for m in "${MODELS[@]}"; do
  python3 harness/run.py --suite data/ps3_cases.jsonl --backend ollama --model "$m"
  python3 harness/run.py --suite data/ps1_cases.jsonl --backend ollama --model "$m"
done

if [[ -n "${BASELINE_BACKEND:-}" ]]; then
  extra=(); [[ -n "${BASELINE_BASE_URL:-}" ]] && extra+=(--base-url "$BASELINE_BASE_URL")
  [[ -n "${BASELINE_KEY_ENV:-}" ]] && extra+=(--api-key-env "$BASELINE_KEY_ENV")
  for s in ps3 ps1; do
    python3 harness/run.py --suite "data/${s}_cases.jsonl" --backend "$BASELINE_BACKEND" \
      --model "$BASELINE_MODEL" ${extra[@]+"${extra[@]}"}
  done
fi

python3 harness/score_ps3.py results/raw/ps3__*.jsonl
python3 harness/judge_ps1.py results/raw/ps1__*.jsonl --backend ollama --model "$JUDGE_MODEL"
echo "Done. See results/ps3_report.md and results/ps1_summary.json."
echo "Then label results/ps1_label_sheet.csv and run: python3 harness/ps1_agreement.py"
