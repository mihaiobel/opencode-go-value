# opencode-go Value

Static GitHub Pages site in vanilla HTML, CSS and JS. No build step. It recommends
the best model per agent role from Go plan quota and Artificial Analysis benchmarks.

- Go plan only, $10/month. Go Plus is ignored.
- Roles: `orchestrator`, `dev`, `reviewer`, `researcher`.
- Only current model versions are considered; older versions of the same model
  are ignored.
- Models flagged as free are excluded: limited-time only, prone to instability
  and timeouts, no dedicated AA slug. They are never recommended and appear
  greyed out in the table.
- A missing AA page is recorded as `aa_status: "no_data"`; nothing is invented.

The recommendation is computed client side in `app.js` from `data/latest.json`.
See the Role matrix in the Methodology section of the page.

## Files

| File | Purpose |
|---|---|
| `index.html` | single page: role picks, sortable top-models table, sources, copy button |
| `app.js` | loads `data/latest.json`, computes the role recommendation, renders the sortable table |
| `styles.css` | warm-paper ledger look, light and dark via system setting, mobile list layout, no external dependencies |
| `data/latest.json` | meta and model data, as-of date in the meta |
| `scripts/fetch_go.py` | updates the JSON from the Go docs, stdlib only |
| `.github/workflows/update-data.yml` | daily cron at 06:00 UTC: refresh data and commit |
| `.github/workflows/pages.yml` | GitHub Pages deploy |
| `refresh-prompt.md` | copy-paste prompt in English for foreign opencode setups |

## Data sources

- `https://opencode.ai/docs/go/` for Go plan prices, monthly limits, estimated `req/5h`.
- `https://opencode.ai/inference/go/v1/models` for full model ids.
- `https://artificialanalysis.ai/models/<slug>` for Intelligence Index, Cost per Task, output speed.

The page shows the models opencode.ai/go lists by default (`meta.featured_ids` in
the JSON, in page order), each with the role it is picked for. Picks come from that
set only. There is no combined score. Update `featured_ids` when the Go page changes.
The Sources section of the page shows only the two canonical root domains,
`https://opencode.ai` and `https://artificialanalysis.ai`.

## Update flow

1. `scripts/fetch_go.py` fetches the Go docs and the models endpoint and parses
   only the Go tables, `data-plan-panel="go"` and not `go-plus`.
2. AA values are carried over per model id from the existing `data/latest.json`.
   New models get `aa_status: "no_data"` and AA values stay `null`.
3. The updated JSON is written to stdout:

   ```bash
   python3 scripts/fetch_go.py --data data/latest.json > data/latest.json.tmp
   python3 -m json.tool data/latest.json.tmp > /dev/null   # validate
   mv data/latest.json.tmp data/latest.json
   ```

4. `.github/workflows/update-data.yml` runs this daily at 06:00 UTC, commits
   `data/latest.json` only when it changed and then starts the Pages deploy.
   The as-of dates in the meta are written along.

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

No external requests are made. `data/latest.json` is loaded via a same-origin `fetch`.

## Enable GitHub Pages

1. Push the repository to GitHub, branch `main`.
2. Set **Settings → Pages → Build and deployment** to **GitHub Actions**.
3. `.github/workflows/pages.yml` deploys the site on every push to `main`. It uses
   `actions/upload-pages-artifact` and `actions/deploy-pages`.
4. For automatic data updates: set **Settings → Actions → General → Workflow permissions**
   to *Read and write*, so the commit step has write access.

## License note

The data comes from [opencode.ai](https://opencode.ai/docs/go/) and
[Artificial Analysis](https://artificialanalysis.ai/) and may be reused only with
attribution. The site code itself is under the MIT license.
