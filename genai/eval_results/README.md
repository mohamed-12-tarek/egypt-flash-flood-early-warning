# Eval results

Where `python -m genai.eval_questions` saves its runs (real Groq agent, 20 fixed questions).

| File | What it is | In git? |
|---|---|---|
| `eval_<UTC timestamp>.json` | one full run | no (ignored) |
| `eval_<UTC timestamp>_partial.json` | a run with `--only ...` | no (ignored) |
| `latest.json` | copy of the newest **full** run | no (ignored) |
| `baseline_*.json` | a run kept on purpose to compare against | **yes** |

To keep a run as evidence: `git add -f genai/eval_results/<file>.json`.

## File format
```json
{
  "run_at_utc": "2026-10-31T21:05:12Z",
  "model": "llama-3.3-70b-versatile",
  "partial": false,
  "total": 20,
  "passed": 20,
  "failed_questions": [],
  "rate_limited_questions": [],
  "logic_failures": [],
  "tokens_total": 0,
  "results": [ { "n": 1, "question": "...", "passed": true, "failed": [], "tools_used": [], "status": "ok",
                 "grounded": true, "data_as_of": "...", "seconds": 4.7, "review": "...", "answer": "..." } ]
}
```
The older `baseline_*.json` is a plain list of the `results` items (the first run, before the metadata header existed).
`genai.eval_questions.load_results(path)` reads both formats.

## Baseline in this folder
`baseline_2026-10-31_before_scope_fix.json`: 19/20 passed. Question 19 failed (an off-topic question answered from
memory); question 20 passed only because its answer contained no digits ("Paris" was answered from memory).
Both are fixed by the scope rule added afterwards, so a new full run should show 20/20.

`failed_questions` = every question that did not pass; `rate_limited_questions` = the ones where Groq answered HTTP 429
(infrastructure, rerun them with `--only`); `logic_failures` = the rest (these are the ones to investigate).
Each row also has `rate_limited`, `tokens_used` and `checks_failed` (why the agent itself rejected a draft, e.g. `numbers: 15`).

## Reading a run
- `passed: false` -> the automatic checks failed; `failed` says which one.
- `review` -> what a human must still read (the script cannot judge wording).
- Compare two runs: open both files and diff the `answer` of the same `n`.
