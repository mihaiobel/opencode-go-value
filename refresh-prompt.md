# Daily prompt

Paste this into any opencode setup to get the same role picks as the page. It can run
every day and answers with a recommendation table.

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

Role matrix:
- orchestrator: largest req/5h among models with AA intel >= 38.
- dev: maximise AA speed times req/5h at AA intel >= 34 and monthly limit >= $30.
- reviewer: highest AA intel at req/5h >= 1000 in a model family not used by
  orchestrator, dev or researcher, where a family is the leading letters of the model id.
- researcher: lowest AA $/Task at req/5h >= 3000, AA intel >= 34, and not the dev model.

Only consider the models https://opencode.ai/go lists by default, not "show more".
Models flagged as free are excluded: limited-time only, unstable and
timeout-prone, no own AA slug.

Output:
1. Role table: role | model id | rationale | key numbers, meaning req/5h, $/month, AA intel, AA speed, AA $/Task.
2. Table of those top models with the recommended role per model; mark free models as "excluded".
3. Call out missing AA data explicitly as "no AA data".
```
