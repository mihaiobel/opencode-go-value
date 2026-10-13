# opencode-go Value

Statische GitHub-Pages-Seite (Vanilla HTML/CSS/JS, **kein Build-Schritt**), die aus
Go-Plan-Quota und Artificial-Analysis-Benchmarks die **beste Modellwahl pro Agentenrolle**
empfiehlt.

- Nur der **Go-Plan ($10/Monat)** — **Go Plus wird ignoriert**.
- Rollen: `orchestrator`, `dev`, `reviewer`, `researcher`.
- **Free-Modelle sind ausgeschlossen** (`longcat-2.5-preview-free`, `step-5-preview-free`):
  nur befristet verfügbar, instabil/Timeout-anfällig, kein eigener AA-Slug. Sie werden nie
  empfohlen und stehen in der Tabelle grau.

Die Empfehlung wird clientseitig in `app.js` aus `data/latest.json` berechnet (siehe
„Rollen-Matrix" im Methodik-Abschnitt der Seite).

## Dateien

| Datei | Zweck |
|---|---|
| `index.html` | einzige Seite: Rollen-Cards, sortierbare Gesamt-Tabelle, Methodik, Quellen, Copy-Button |
| `app.js` | lädt `data/latest.json`, berechnet Rollen-Empfehlung, rendert Tabelle (sortierbar) |
| `styles.css` | schlichtes Dark-Theme, mobil lesbar, keine externen Abhängigkeiten |
| `data/latest.json` | Meta + Modelldaten (Stand im Meta) |
| `scripts/fetch_go.py` | Aktualisiert das JSON aus den Go-Docs (nur Stdlib) |
| `.github/workflows/update-data.yml` | täglicher Cron (06:00 UTC): Daten aktualisieren + committen |
| `.github/workflows/pages.yml` | GitHub-Pages-Deploy |
| `refresh-prompt.md` | Copy-Paste-Prompt (DE/EN) für fremde opencode-Setups |

## Datenquellen

- `https://opencode.ai/docs/go/` — Go-Plan-Preise, Monatslimits, geschätzte `req/5h`.
- `https://opencode.ai/inference/go/v1/models` — vollständige Modell-IDs.
- `https://artificialanalysis.ai/models/<slug>` — Intelligence Index, Cost per Task, Output-Speed.

Fehlende AA-Seiten werden als `aa_status: "no_data"` geführt — es wird **nichts geraten**.

## Update-Ablauf

1. `scripts/fetch_go.py` lädt die Go-Docs und den Models-Endpoint, parst **nur** die
   Go-Tabellen (`data-plan-panel="go"`, nicht `go-plus`).
2. AA-Werte werden per Modell-ID aus dem vorhandenen `data/latest.json` übernommen.
   **Neue** Modelle bekommen `aa_status: "no_data"` (AA-Werte bleiben `null`).
3. Ausgabe des aktualisierten JSON auf **stdout**:

   ```bash
   python3 scripts/fetch_go.py --data data/latest.json > data/latest.json.tmp
   python3 -m json.tool data/latest.json.tmp > /dev/null   # validieren
   mv data/latest.json.tmp data/latest.json
   ```

4. `.github/workflows/update-data.yml` macht das täglich um 06:00 UTC und committet
   `data/latest.json` nur bei Änderung (Stand-Datum im Meta wird mitgeschrieben).

Hilfe und Optionen:

```bash
python3 scripts/fetch_go.py --help
```

## Lokal testen

```bash
cd opencode-go-value
python3 -m http.server 8000
# dann http://localhost:8000/ im Browser öffnen
```

Es werden keine externen Requests abgesetzt; `data/latest.json` wird per
Same-Origin-`fetch` geladen.

## GitHub Pages aktivieren

1. Repository auf GitHub pushen (Branch `main`).
2. **Settings → Pages → Build and deployment** auf **GitHub Actions** stellen.
3. `.github/workflows/pages.yml` deployt die Seite bei jedem Push auf `main`
   (`actions/upload-pages-artifact` + `actions/deploy-pages`).
4. Für automatische Daten-Updates: **Settings → Actions → General → Workflow permissions**
   auf *Read and write* (der Commit-Step braucht Schreibrechte).

## Lizenz-Hinweis

Die **Daten** stammen von [opencode.ai](https://opencode.ai/docs/go/) und
[Artificial Analysis](https://artificialanalysis.ai/) und dürfen nur **mit Quellenangabe**
weiterverwendet werden. Der Seiten-Code selbst steht unter der MIT-Lizenz.
