Open-Weight Collections Challenge (PS-3, plus PS-1 pilot)
(FDE Assignment) 

In a collections call the tool call *is* the outcome. If `capture_ptp` doesn't fire
when a borrower promises to pay, the money is lost silently: the call sounds fine and the
transcript reads fine. I tested how often small open-weight models (Qwen3.5-4B and 9B)
get the tool call right when the borrower speaks Hinglish or Marathi instead of English.

## What's here

| Path | What it is |
| --- | --- |
| `data/ps3_cases.jsonl` | The PS-3 test suite: 200 borrower turns with the expected tool and arguments. Built by `data/build_ps3_cases.py`. |
| `data/ps1_cases.jsonl` | PS-1 pilot: 32 adversarial borrower turns, each labelled with the violation it targets. |
| `schemas/tools.json`, `prompts/system_prompt.txt` | The fixed tool schemas and system prompt from the brief, unchanged. |
| `harness/run.py` | Sends each case to a model and logs the raw response. Works with Ollama, any OpenAI-compatible API, Anthropic, or a mock. |
| `harness/score_ps3.py` | Scores PS-3. Definitions are in `METRICS.md`, written before any model was run. |
| `harness/judge_ps1.py`, `harness/ps1_agreement.py` | PS-1: an LLM judge, plus judge-vs-human agreement (Cohen's κ). |
| `results/` | `ps3_report.md` (tables), `ps3_scored.jsonl` (every case), `raw/` (every model response), `ps1_judged.jsonl`, `ps1_label_sheet.csv`. |
| `run_log.txt` | Console log of the full overnight run. |
| `FINDINGS.md` | What I found, what I'm unsure about, and limitations (4 pages max). |
| `DESIGN_NOTES.md` | How I would approach PS-2, PS-4, PS-5 and PS-6. |

## How the test works

I wrote 80 borrower intents twice, once in English and once in Hinglish, with the **same
expected answer**. So the English-vs-Hinglish gap is measured on the same 80 situations,
not on two different test sets. On top of that: 20 Marathi turns and 20 deliberately
vague ones ("dekhta hoon, agle hafte kuch karta hoon") to see whether the model invents a
promise that wasn't made.

A case only counts as correct if the right tool fires **and** the amount, date or type is
right **and** the call is valid against the schema. A `capture_ptp` with the wrong date is
a wrong answer.

## Results (Q4 on a 2017 Intel MacBook Pro, CPU only)

| | Qwen3.5-4B | Qwen3.5-9B |
| --- | --- | --- |
| English, full-correct (n=80) | 77.5% | 75.0% |
| Hinglish, full-correct (n=80) | 61.3% | 52.5% |
| **Gap (EN − HI)** | **−16.2 pts** (p=0.03) | **−22.5 pts** (p=0.0001) |
| Amount errors when the right tool fired, EN / HI | 0 / 12 | 0 / 9 |
| Marathi, full-correct (n=20) | 65% | 65% |
| Distress turns escalated to a human (n=11) | 10 | 5 |
| No-tool turns where it fired anyway (n=14) | 8 | 0 |

The short version: the gap is mostly **Hindi number words** (*dhai hazaar* recorded as
1,250, *pandrah sau* as 15,000). The bigger 9B model is *worse* in Hinglish because it
often doesn't fire the tool at all, and it missed 6 of 11 distress escalations.

The PS-1 pilot's LLM judge turned out to be unreliable (it flags correct replies), so its
violation rates are only reported alongside human-label agreement. See `FINDINGS.md` §5.

Full tables: `results/ps3_report.md`. The write-up is in `FINDINGS.md`.

## Settings held fixed

- The system prompt and tool schemas are verbatim from the brief. The only addition is one
  line giving today's date ("Thursday, 2026-10-01"), so "kal", "parso" and "Saturday" have
  a right answer. It's the same for every model and every case.
- Temperature 0, seed 42, thinking mode off. The harness warns if any thinking tokens show up.
- A fictional lender ("Suvidha Finance") and four fictional borrowers at 5, 30 and 90 DPD.
  No real data.

## How to run

Needs Python 3.9+ (no packages to install) and [Ollama](https://ollama.com).

    ollama serve                 # in one terminal, leave running
    ollama pull qwen3.5:4b
    ollama pull qwen3.5:9b
    bash run_all.sh              # runs both suites on both models, scores, judges

Hosted baseline (optional), e.g. Gemini through its OpenAI-compatible endpoint:

    export GEMINI_API_KEY="your-key"
    BASELINE_BACKEND=openai BASELINE_MODEL=gemini-flash-lite-latest \
    BASELINE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai \
    BASELINE_KEY_ENV=GEMINI_API_KEY bash run_all.sh

Dry run without a model: `python3 harness/run.py --suite data/ps3_cases.jsonl --backend mock --model mock`

Runs resume: if one stops halfway, run the same command again and it skips finished cases.

## Limits

- **Q4 only.** The brief says not to treat Q4 results as production conclusions; PS-5 is
  for that. Latency on a CPU-only laptop isn't meaningful either, so I don't report it.
- **The test cases were drafted with an AI assistant** and reviewed by me. A second native
  speaker hasn't reviewed them. Hinglish is romanised only.
- **Single turns.** A promise built up over several turns isn't tested.
- **Marathi and vague sets are small** (20 each), so read those numbers loosely.
- **PS-1 is a pilot** (32 turns, one rater checking AI pre-labels), not the 150+ suite the brief asks for.
- **Some expected answers are judgment calls**, e.g. "I already paid" → `mark_dispute`.
  The vague cases accept more than one answer for this reason.

## How this was built

As the brief allows, I used an AI coding assistant (Claude Code). It wrote some of harness
and scorer code, while i did the rest, drafted the test cases and the PS-1 pre-labels, and helped draft the
write-up. I chose the problem and scope, set up and ran every experiment on my machine,
reviewed the cases, checked all 64 PS-1 labels, and stand behind the findings.
