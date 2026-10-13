# Daily-Prompt: opencode-Go-Modellwahl neu bewerten

Copy-Paste-Prompt für ein **fremdes** opencode-Setup, das dieselbe Rollen-Logik wie
`opencode-go-value` anwenden will. Täglich ausführbar. Antwort = Empfehlungstabelle.

---

## Deutsch

```text
Werte die opencode-Go-Modelle ($10-Plan, KEIN Go Plus) neu aus und empfiehl je
Agentenrolle das beste Modell.

Quellen (Primärquellen, nichts erfinden):
- https://opencode.ai/docs/go/  -> nur die Go-Spalte der Preis- und Requests-Tabellen
  (nicht Go Plus). Lies req/5h, Monatslimit ($), In/Out/Cached-Preise ($/1M).
- https://opencode.ai/inference/go/v1/models  -> vollständige Modell-IDs.
- https://artificialanalysis.ai/models/<slug>  -> Intelligence Index, Cost per Task ($),
  Output-Speed (t/s). Fehlt die AA-Seite (404): als "keine AA-Daten" markieren, nicht raten.

Rollen-Matrix:
- orchestrator: größte req/5h unter Modellen mit AA-Intel >= 38
  (ODER muse-spark-Sonderfall: no_data, aber größte Quota).
- dev: maximiert (AA-Speed × req/5h) bei AA-Intel >= 34 und Monatslimit >= $30.
- reviewer: höchster AA-Intel bei req/5h >= 1000 und in einer Modellfamilie, die weder
  dev noch researcher belegen (Familie = ID-Präfix, z. B. deepseek / mimo / claude).
- researcher: kleinster AA-$/Task bei req/5h >= 3000, AA-Intel >= 34 und nicht das dev-Modell.

Free-Modelle (longcat-2.5-preview-free, step-5-preview-free) sind ausgeschlossen:
befristet (limited time), instabil/Timeout-anfällig, kein eigener AA-Slug.

Ausgabe:
1. Tabelle der Rollen: Rolle | Modell-ID | Begründung | Kernzahlen (req/5h, $/Monat, AA-Intel, AA-Speed, AA-$/Task).
2. Vollständige Modelltabelle mit allen Go-Modellen; Free-Modelle als "ausgeschlossen" markiert.
3. Fehlende AA-Daten explizit als "keine AA-Daten" kennzeichnen.
```

---

## English

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
