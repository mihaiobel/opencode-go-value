# opencode-go Value

Static GitHub Pages site (vanilla HTML/CSS/JS, **no build step**) that recommends
the **best model per agent role** from Go plan quota and Artificial Analysis
benchmarks.

- **Go plan only ($10/month)** — **Go Plus is ignored**.
- Roles: `orchestrator`, `dev`, `reviewer`, `researcher`.
- **Free models are excluded** (`longcat-2.5-preview-free`, `step-5-preview-free`):
  available for a limited time only, prone to instability/timeouts, no dedicated AA
  slug. They are never recommended and appear greyed out in the table.

The recommendation is computed client-side in `app.js` from `data/latest.json`
(see the "Role matrix" in the Methodology section of the page).

## Files

| File | Purpose |
|---|---|
| `index.html` | single page: role cards, sortable full table, methodology, sources, copy button |
| `app.js` | loads `data/latest.json`, computes the role recommendation, renders the sortable table |
| `styles.css` | plain dark theme, mobile readable, no external dependencies |
| `data/latest.json` | meta + model data (as-of date in the meta) |
| `scripts/fetch_go.py` | updates the JSON from the Go docs (stdlib only) |
| `.github/workflows/update-data.yml` | daily cron (06:00 UTC): refresh data + commit |
| `.github/workflows/pages.yml` | GitHub Pages deploy |
| `refresh-prompt.md` | copy-paste prompt (EN) for foreign opencode setups |

## Data sources

- `https://opencode.ai/docs/go/` — Go plan prices, monthly limits, estimated `req/5h`.
- `https://opencode.ai/inference/go/v1/models` — full model ids.
- `https://artificialanalysis.ai/models/<slug>` — Intelligence Index, Cost per Task, output speed.

Missing AA pages are recorded as `aa_status: "no_data"` — **nothing is guessed**.
The Sources section of the page shows only the two canonical root domains
(`https://opencode.ai` and `https://artificialanalysis.ai`).

## Update flow

1. `scripts/fetch_go.py` fetches the Go docs and the models endpoint and parses
   **only** the Go tables (`data-plan-panel="go"`, not `go-plus`).
2. AA values are carried over per model id from the existing `data/latest.json`.
   **New** models get `aa_status: "no_data"` (AA values stay `null`).
3. The updated JSON is written to **stdout**:

   ```bash
   python3 scripts/fetch_go.py --data data/latest.json > data/latest.json.tmp
   python3 -m json.tool data/latest.json.tmp > /dev/null   # validate
   mv data/latest.json.tmp data/latest.json
   ```

4. `.github/workflows/update-data.yml` does this daily at 06:00 UTC and commits
   `data/latest.json` only when it changed (the as-of date in the meta is written along).

Help and options:

```bash
python3 scripts/fetch_go.py --help
```

## Test locally

```bash
cd opencode-go-value
python3 -m http.server 8000
# then open http://localhost:8000/ in a browser
```

No external requests are made; `data/latest.json` is loaded via a same-origin
`fetch`.

## Enable GitHub Pages

1. Push the repository to GitHub (branch `main`).
2. Set **Settings → Pages → Build and deployment** to **GitHub Actions**.
3. `.github/workflows/pages.yml` deploys the site on every push to `main`
   (`actions/upload-pages-artifact` + `actions/deploy-pages`).
4. For automatic data updates: set **Settings → Actions → General → Workflow permissions**
   to *Read and write* (the commit step needs write access).

## License note

The **data** comes from [opencode.ai](https://opencode.ai/docs/go/) and
[Artificial Analysis](https://artificialanalysis.ai/) and may be reused only **with
attribution**. The site code itself is under the MIT license.
