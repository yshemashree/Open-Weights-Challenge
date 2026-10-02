# PS-3 metric definitions

Written and committed before any model was run. The scorer (`harness/score_ps3.py`)
implements exactly these definitions.

## Unit of evaluation
One case is one borrower turn after a fixed agent opener. The model sees the fixed
system prompt (`prompts/system_prompt.txt`), one date-anchor line, the five fixed tool
schemas, the opener and the borrower turn. We score **the tool calls in that single
response**. Temperature 0, seed 42, thinking off.

## Gold
Each case lists one or more acceptable outcomes (`accept`). An outcome is either
*no tool call* or a tool name plus allowed values for the scored arguments. Core and
Marathi cases have exactly one outcome. Ambiguous cases may have several. The case is
scored against whichever acceptable outcome it matches best.

## `log_disposition` handling
The prompt says every call *ends* with `log_disposition`, so a model may add it to any
turn. Therefore:
- If the expected tool is an action (`capture_ptp`, `send_payment_link`, `mark_dispute`,
  `escalate_human`), an extra `log_disposition` is ignored.
- If the expected tool is `log_disposition` (wrong number, callback, refusal), it must
  carry the right `code` and **no** action tool may fire.
- If the expected outcome is *no tool*, any call, including `log_disposition`, is spurious.
  Those turns are mid-call, so ending the call is wrong.

## Per-case classification (tool level)
| Kind | Meaning |
|---|---|
| correct | The expected tool fired (per the rules above) |
| missed | A tool was expected, and no tool fired (or only `log_disposition` fired when an action was expected) |
| wrong_tool | A tool was expected, and a different tool fired |
| spurious | No tool was expected, and a tool fired |

## Metrics
| Metric | Definition | Denominator |
|---|---|---|
| **Full-correct** (headline) | Right tool **and** all scored arguments right **and** the matched call is schema-valid | all cases |
| Correct tool | Tool level only | all cases |
| Argument accuracy, given tool | Every scored argument matches the gold | cases where the right tool fired |
| Missed-call rate | `missed` | cases that expect a tool |
| Wrong-tool rate | `wrong_tool` | cases that expect a tool |
| Spurious-call rate | `spurious` | cases where the gold is "no tool" |
| Malformed rate | At least one call violates its schema: unknown tool, unparseable JSON, missing required field, wrong type, value outside the enum, non-ISO date | cases with at least one call |
| Leaked-as-text | No structured call, but the reply text names a tool (the model "said" the call instead of making it) | all cases |
| Confidence agreement | `confidence` matches the gold firm/tentative label. **Secondary:** it is optional in the schema, so it is never part of full-correct | PTP cases where the model supplied it |

**Argument matching.** Amounts match within ±0.5. A string like `"5000"` matches on
value but is still counted as malformed. Dates match on `YYYY-MM-DD`. Enums are
case-insensitive for value matching but must be exact for validity. Free-text fields
(`borrower_statement`, `notes`) are never scored.

## Headline number: the English-vs-Hinglish delta
Full-correct on the 80 English core cases minus full-correct on their 80 Hinglish
pairs. Same intent, same gold, same profile; only the language differs. Significance is
an exact two-sided McNemar test on the discordant pairs. 95% Wilson intervals are
reported for each rate.

## Ambiguous set
- **Over-fire**: a tool fired on a case where *no tool* was an acceptable answer, and the
  call matched no acceptable outcome.
- **Under-fire**: no tool fired on a case where every acceptable answer is a tool call.
