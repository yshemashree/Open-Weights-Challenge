# Design notes for the problem statements not submitted in full

These are short plans, not results. Each one says what I would measure, how, the
main trap, and how it builds on what is already in this repo.

## PS-1 · Guardrail Gauntlet (pilot included)
- **Included:** 32 adversarial turns (`data/ps1_cases.jsonl`) covering all 8 violation
  categories in English/Hinglish pairs plus Marathi, an LLM judge (`prompts/judge_prompt.txt`)
  and a judge-vs-human agreement script (Cohen's κ).
- **To reach the full brief:** 150+ turns, multi-turn escalation (abuse that builds over
  4–5 turns, where a single-turn test under-reports V1), and a second independent native rater.
- **Trap:** a judge that is the same model family as the agent tends to excuse its own
  failure modes. Use a different-family judge, and report agreement per language,
  because judge quality is also likely to drop in Hinglish.

## PS-2 · Code-Mix Register Test
- **Plan:** a text → TTS → audio harness, run on the same scenario at 5, 30 and 90 DPD,
  scored with the section 6.2 rubric by two raters who listen to the audio rather than read it.
- **What I expect to find:** numerals and currency are the main audio failure.
  "₹12,500" read as "rupees one two five zero zero", or romanised Hinglish read with
  English phonetics. These failures are invisible in a transcript.
- **Cheap first step:** run the PS-3 replies through TTS and listen to just the amounts and dates.

## PS-4 · p95 under month-end load (Track 2)
- **Why not on a laptop:** Ollama serves one stream at a time, so a concurrency sweep on
  it measures queueing, not batching. The brief says this explicitly.
- **Plan:** vLLM with continuous batching and thinking off; a sweep at 1/10/25/50/100
  concurrent calls driven through the LiveKit loop; report p50/p95/p99 TTFT and
  inter-token latency.
- **Saturation threshold:** state it before running, e.g. a p95 TTFT above ~800 ms, beyond
  which a borrower notices the pause and talks over the agent.
- **Trap:** synthetic prompts that are too short. Real turns carry the full system prompt
  plus history, so prompt length should grow over the call.

## PS-5 · Quantization cliff (Track 2)
- **This repo's PS-3 suite is the measuring instrument.** Re-run `harness/run.py`
  unchanged at Q4, Q8, FP8 and BF16, on one GPU, with the same seed, prompt and suite.
- **What I expect to find:** malformed-call rate and argument accuracy (dates, Hindi
  number words) degrade before tool selection does. Guardrail adherence should be
  plotted as a separate curve.
- **Control:** Ollama Q4 and vLLM FP8 differ in more than precision (different runtime,
  different chat template). Compare across precisions within one runtime, or state the
  confound.

## PS-6 · Domain LoRA (Track 2, stretch)
- **Plan:** a LoRA on the synthetic corpus, evaluated before and after on held-out
  PS-3 and PS-1 cases. **Any rise in violation rate disqualifies it**, regardless of task gains.
- **Main risk:** fine-tuning on "successful" collections transcripts teaches pressure,
  which can erode V1/V4 refusals. Check the safety regression first, not last.
- **Split:** keep the paired English/Hinglish cases out of training, so the language delta
  stays a clean held-out measurement.
