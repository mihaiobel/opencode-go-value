# Daily prompt: re-evaluate the opencode Go model choice

Copy-paste prompt for a **foreign** opencode setup that wants to apply the same
role logic as `opencode-go-value`. Runnable daily. The answer is a recommendation
table.

---

```text
Re-evaluate the opencode Go models ($10 plan, NOT Go Plus) and recommend the best
model per agent role.

Sources (primary sources only, never guess):
- https://opencode.ai/docs/go/  -> the Go column of the pricing and requests tables only
  (not Go Plus). Read req/5h, monthly limit ($), in/out/cached prices ($/1M).
- https://opencode.ai/inference/go/v1/models  -> full model ids.
- https://artificialanalysis.ai/models/<slug>  -> Intelligence Index, Cost per Task ($),
  output speed (t/s). If the AA page is missing (404): mark it "no AA data", do not guess.

Role matrix:
- orchestrator: largest req/5h among models with AA intel >= 38
  (OR the muse-spark special case: no_data but largest quota).
- dev: maximise (AA speed × req/5h) at AA intel >= 34 and monthly limit >= $30.
- reviewer: highest AA intel at req/5h >= 1000 in a model family not used by
  dev or researcher (family = id prefix, e.g. deepseek / mimo / claude).
- researcher: lowest AA $/Task at req/5h >= 3000, AA intel >= 34, not the dev model.

Free models (longcat-2.5-preview-free, step-5-preview-free) are excluded:
limited-time only, unstable/timeout-prone, no own AA slug.

Output:
1. Role table: role | model id | rationale | key numbers (req/5h, $/month, AA intel, AA speed, AA $/Task).
2. Full model table with every Go model; mark free models as "excluded".
3. Call out missing AA data explicitly as "no AA data".
```
