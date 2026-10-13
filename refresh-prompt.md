# Daily prompt: re-evaluate the opencode Go model choice

Copy-paste prompt for a foreign opencode setup that wants the same role logic as
`opencode-go-value`. Runnable daily. The answer is a recommendation table.

---

```text
Re-evaluate the opencode Go models, $10 plan, NOT Go Plus, and recommend the best
model per agent role.

Sources, primary only, never guess:
- https://opencode.ai/docs/go/  -> the Go column of the pricing and requests tables
  only, not Go Plus. Read req/5h, monthly limit in USD, in/out/cached prices in $/1M.
- https://opencode.ai/inference/go/v1/models  -> full model ids.
- https://artificialanalysis.ai/models/<slug>  -> Intelligence Index, Cost per Task in USD,
  output speed in t/s. If the AA page is missing with a 404, mark it "no AA data", do not guess.
- https://lmarena.ai/leaderboard/text  -> LMArena Overall score, as of 2026-10-08. If the
  entry is missing, mark it "missing" and do not guess.

Role matrix:
- orchestrator: largest req/5h among models with AA intel >= 38, or the muse-spark
  special case with no AA data and the largest quota.
- dev: maximise AA speed times req/5h at AA intel >= 34 and monthly limit >= $30.
- reviewer: highest AA intel at req/5h >= 1000 in a model family not used by
  dev or researcher, where a family is the id prefix such as deepseek, mimo or claude.
- researcher: lowest AA $/Task at req/5h >= 3000, AA intel >= 34, and not the dev model.

Free models longcat-2.5-preview-free and step-5-preview-free are excluded:
limited-time only, unstable and timeout-prone, no own AA slug.

Score: compute a combined score per model as the mean of the normalised AA and
LMArena values, each mapped to 0 to 100. Mark mapped and missing Arena values in
the table.

Output:
1. Role table: role | model id | rationale | key numbers, meaning req/5h, $/month, AA intel, AA speed, AA $/Task.
2. Full model table with every Go model; mark free models as "excluded".
3. Call out missing AA data explicitly as "no AA data".
```
