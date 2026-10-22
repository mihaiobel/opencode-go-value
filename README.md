# opencode-go Value

Which opencode Go model should run which agent role? This page picks one model each for
orchestrator, dev, reviewer and researcher, based on the $10 Go plan quota and
Artificial Analysis benchmarks.

Live page: https://mihaiobel.github.io/opencode-go-value/

## How it works

- Only the $10 Go plan counts. Go Plus is ignored.
- Only the models that opencode.ai/go lists by default are considered, in that order.
  The list is `meta.featured_ids` in `data/latest.json`.
- Free models are never picked. They are limited in time, unstable and have no
  Artificial Analysis page.
- A model without Artificial Analysis data is marked `aa_status: "no_data"`. Nothing is guessed.
- The picks are computed in the browser by `app.js`. The rules are in the daily prompt on the page.

## Files

| File | Purpose |
|---|---|
| `index.html` | The page: role picks, sortable table of top models, daily prompt |
| `app.js` | Loads the data, computes the picks, renders the table |
| `styles.css` | Styling, light and dark mode, no external dependencies |
| `data/latest.json` | Model data and metadata |
| `scripts/fetch_go.py` | Refreshes the data from the Go docs, standard library only |
| `scripts/audit_aa.py` | Looks up Artificial Analysis values for models without data |
| `refresh-prompt.md` | Prompt to run the same evaluation in any opencode setup |
| `.github/workflows/update-data.yml` | Daily data refresh at 06:00 UTC |
| `.github/workflows/pages.yml` | Deploys the page to GitHub Pages |

## Data sources

- https://opencode.ai/docs/go/ for prices, monthly limits and estimated requests per 5 hours
- https://opencode.ai/inference/go/v1/models for model ids
- https://artificialanalysis.ai/models/ for Intelligence Index, cost per task and output speed

## Updating the data

`scripts/fetch_go.py` reads the Go tables from the docs and writes the updated JSON to stdout.
Artificial Analysis values are carried over by model id. New models start without them.
`meta.featured_ids` is kept as is, so update it by hand when the Go page changes.

```bash
python3 scripts/fetch_go.py --data data/latest.json > data/latest.json.tmp
python3 -m json.tool data/latest.json.tmp > /dev/null
mv data/latest.json.tmp data/latest.json
```

The workflow does this every day, commits `data/latest.json` if it changed and starts the deploy.

## Run locally

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000/. The page makes no external requests.

## Deploy

1. Push to `main`.
2. Set Settings > Pages > Source to GitHub Actions.
3. Set Settings > Actions > General > Workflow permissions to Read and write, so the daily commit works.

## License

The site code is MIT. The data comes from [opencode.ai](https://opencode.ai/docs/go/) and
[Artificial Analysis](https://artificialanalysis.ai/) and may be reused with attribution.
