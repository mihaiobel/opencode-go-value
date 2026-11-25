#!/usr/bin/env python3
"""Fetch the opencode Go plan catalog and emit an updated data/latest.json on stdout.

Only the standard library is used (urllib, re, json, ...).

What it does
------------
1. Downloads https://opencode.ai/console/go (Go limits table) and
   https://opencode.ai/inference/go/v1/models (model ids, names, prices, Go monthly usage).
2. Reads the **Go plan** values only: the "Est. requests / 5 hr" and "Monthly limit"
   cells for the ``go`` plan. The Go Plus values are ignored on purpose.
   The table is located by its ``data-allowance-type`` cells, not by heading text,
   so the page layout can change without breaking the parser.
3. Maps every table row to a model id via the models endpoint (normalized display
   name or id). Prices come from the endpoint's ``cost`` field.
4. Carries the Artificial Analysis values (aa_intelligence, aa_speed_tps,
   aa_cost_per_task, aa_status) over from the existing ``data/latest.json`` by model id.
   ``meta.featured_ids`` (the models opencode.ai/go lists by default) is kept as is.
5. Detects new model ids by diffing against the existing file. New models get
   ``aa_status: "no_data"`` and null AA fields (benchmarks are never guessed).
6. Prints the updated JSON to stdout. Diagnostics go to stderr, so stdout stays
   valid JSON and can be redirected straight into ``data/latest.json``.

History: until 2026-11 the data came from ``/docs/go/`` (tables with
``data-plan-panel``). That page was restructured (now a redirect to
``/docs/console/go/`` without the limits), hence the switch to the console page.

Example
-------
    python3 scripts/fetch_go.py > data/latest.json
    python3 scripts/fetch_go.py --data data/latest.json --insecure > /tmp/latest.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import ssl
import sys
import urllib.request
from html import unescape

CONSOLE_URL = "https://opencode.ai/console/go"
MODELS_URL = "https://opencode.ai/inference/go/v1/models"
LEGACY_DOCS_URLS = ("https://opencode.ai/docs/go/", "https://opencode.ai/docs/console/go/")
USER_AGENT = "opencode-go-value/1.0 (+https://opencode.ai/console/go)"

FREE_REASON = (
    "Free for a limited time only, no own Artificial Analysis page, no benchmark data."
)


def _fetch(url: str, insecure: bool = False, timeout: int = 30) -> str:
    """Fetch *url* and return the decoded body (redirects are followed)."""
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", "replace")


def _strip_tags(cell: str) -> str:
    """Turn an HTML fragment into plain text."""
    cell = re.sub(r"(?is)<small\b.*?</small>", " ", cell)
    cell = re.sub(r"(?i)<br\s*/?>", " ", cell)
    cell = re.sub(r"<[^>]+>", "", cell)
    cell = unescape(cell)
    return re.sub(r"\s+", " ", cell).strip()


def _num(text):
    """Parse a currency/number cell into a float, or None when not numeric.

    ``∞`` / ``Unlimited`` / ``-`` / ``Free`` mean "no numeric limit" and give None.
    """
    if text is None:
        return None
    cleaned = str(text).replace(",", "").replace("$", "").strip()
    if cleaned in ("", "-", "∞") or cleaned.lower().startswith(("unlimited", "free")):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _norm(name: str) -> str:
    """Loose key for matching display names against model ids: 'GLM-5.3-Flash' -> 'glm 5 3 flash'."""
    return re.sub(r"[^a-z0-9]+", " ", unescape(name).lower()).strip()


def _slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"\s+", "-", s.strip())
    return re.sub(r"[^a-z0-9.\-]", "", s)


def parse_console_rows(html: str) -> list[dict]:
    """Return ``[{name, requests_per_5h, monthly_limit_usd}]`` for the Go plan.

    The limits table is the one whose cells carry both ``data-allowance-type="requests"``
    and ``data-allowance-type="usage"``. Each cell holds an sr-only summary such as
    ``Go: 98; Go Plus: 392``; only the ``Go:`` part is used.
    """
    table = None
    for match in re.finditer(r"(?is)<table\b.*?</table>", html):
        block = match.group(0)
        if 'data-allowance-type="requests"' in block and 'data-allowance-type="usage"' in block:
            table = block
            break
    if table is None:
        raise ValueError("Go limits table (requests / monthly usage) not found on console page")

    rows: list[dict] = []
    for row in re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", table):
        title = re.search(r'data-layer="model-name"[^>]*\btitle="([^"]*)"', row)
        if not title:
            continue  # header row or unrelated row
        name = unescape(title.group(1)).strip()

        values: dict[str, object] = {}
        for kind in ("requests", "usage"):
            cell = re.search(
                rf'(?is)<td\b[^>]*data-allowance-type="{kind}"[^>]*>(.*?)</td>', row)
            summary = re.search(r'<span class="sr-only">([^<]*)</span>', cell.group(1)) if cell else None
            go = re.search(r"(?:^|;)\s*Go:\s*([^;]+)", unescape(summary.group(1))) if summary else None
            if go is None:
                raise ValueError(f"no Go value for {name!r} ({kind}) on console page")
            values[kind] = _num(go.group(1))

        rows.append({
            "name": name,
            "requests_per_5h": values["requests"],
            "monthly_limit_usd": values["usage"],
        })

    if not rows:
        raise ValueError("Go limits table contained no model rows")
    return rows


def _api_prices(model: dict) -> tuple:
    text = (model.get("cost") or {}).get("text") or {}
    inp = text.get("input") or {}
    out = text.get("output") or {}
    cache = inp.get("cache") or {}
    return inp.get("price"), out.get("price"), cache.get("read")


def build_catalog(rows: list[dict], api_models: list[dict],
                  previous: dict | None = None) -> dict[str, dict]:
    """Join console rows with the models endpoint (ids, prices) into a catalog keyed by id.

    Rows the endpoint does not know keep the id slug and the prices from *previous*
    (the existing data file), so the last known price is shown instead of nothing.
    """
    previous = previous or {}
    index: dict[str, dict] = {}
    for m in api_models:
        mid = m.get("id")
        if not mid:
            continue
        index.setdefault(_norm(mid), m)
        if m.get("name"):
            index.setdefault(_norm(m["name"]), m)

    catalog: dict[str, dict] = {}
    for row in rows:
        api = index.get(_norm(row["name"]))
        if api is None:
            model_id = _slug(row["name"])
            old = previous.get(model_id, {})
            print(f"warning: {row['name']!r} not in models endpoint, "
                  f"keeping last known prices for {model_id!r}", file=sys.stderr)
            price_in, price_out, price_cached = (
                old.get("price_in"), old.get("price_out"), old.get("price_cached"))
        else:
            model_id = api["id"]
            price_in, price_out, price_cached = _api_prices(api)
        if model_id in catalog:
            continue
        free = "free" in row["name"].lower() or model_id.endswith("-free")
        catalog[model_id] = {
            "id": model_id,
            "name": row["name"],
            "monthly_limit_usd": row["monthly_limit_usd"],
            "requests_per_5h": row["requests_per_5h"],
            "price_in": 0.0 if free else price_in,
            "price_out": 0.0 if free else price_out,
            "price_cached": 0.0 if free else price_cached,
            "free": free,
        }
    if not catalog:
        raise ValueError("Go limits table produced an empty catalog")
    return catalog


def _load_existing(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"meta": {}, "models": []}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: could not read {path}: {exc}", file=sys.stderr)
        return {"meta": {}, "models": []}


def build(existing: dict, catalog: dict, model_ids: list[str], console_url: str,
          models_url: str) -> tuple[dict, list[str]]:
    old_by_id = {m.get("id"): m for m in existing.get("models", []) if m.get("id")}
    new_ids = [mid for mid in catalog if mid not in old_by_id]

    models: list[dict] = []
    for mid in catalog:
        entry = catalog[mid]
        old = old_by_id.get(mid, {})
        out = {
            "id": mid,
            "monthly_limit_usd": entry["monthly_limit_usd"],
            "requests_per_5h": entry["requests_per_5h"],
            "price_in": entry["price_in"],
            "price_out": entry["price_out"],
            "price_cached": entry["price_cached"],
        }
        if old:
            # carry AA values over verbatim
            for key in ("aa_intelligence", "aa_speed_tps", "aa_cost_per_task", "aa_status"):
                out[key] = old.get(key)
            if not out.get("aa_status"):
                out["aa_status"] = "no_data"
        else:
            out["aa_intelligence"] = None
            out["aa_speed_tps"] = None
            out["aa_cost_per_task"] = None
            out["aa_status"] = "no_data"
        out["free"] = entry["free"]
        if entry["free"]:
            out["excluded_reason"] = old.get("excluded_reason", FREE_REASON)
        models.append(out)

    # Stable order: keep the existing order for known ids, append new ids at the end.
    order = {m.get("id"): i for i, m in enumerate(existing.get("models", []))}
    models.sort(key=lambda m: (0, order[m["id"]]) if m["id"] in order else (1, m["id"]))

    meta = dict(existing.get("meta", {}))
    meta["as_of"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    meta.setdefault("aa_index_version", "Artificial Analysis Intelligence Index v4.3.2")
    meta.setdefault("plan", "opencode-go ($10/month)")
    # opencode sources first (current pages), then the non-opencode sources kept as they were
    kept = [u for u in meta.get("source_urls", [])
            if u not in (console_url, models_url, *LEGACY_DOCS_URLS)]
    meta["source_urls"] = [console_url, models_url] + kept
    if new_ids:
        meta["new_models"] = new_ids
    else:
        meta.pop("new_models", None)
    # ids the models endpoint knows but the Go limits table does not list
    undocumented = sorted(set(model_ids) - set(catalog))
    if undocumented:
        meta["undocumented_ids"] = undocumented

    return {"meta": meta, "models": models}, new_ids


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="fetch_go.py",
        description=(
            "Fetch the opencode Go plan limits (Go, not Go Plus), carry over the "
            "Artificial Analysis values from data/latest.json and print the updated "
            "JSON catalog to stdout."
        ),
        epilog=(
            "Examples:\n"
            "  python3 scripts/fetch_go.py > data/latest.json\n"
            "  python3 scripts/fetch_go.py --data data/latest.json --insecure\n"
            "\n"
            "stdout is always valid JSON; progress and warnings go to stderr."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data", default="data/latest.json",
                        help="existing catalog to diff against / carry AA values from "
                             "(default: data/latest.json)")
    parser.add_argument("--console-url", default=CONSOLE_URL,
                        help=f"console page with the Go limits table (default: {CONSOLE_URL})")
    parser.add_argument("--models-url", default=MODELS_URL,
                        help=f"models endpoint (default: {MODELS_URL})")
    parser.add_argument("--timeout", type=int, default=30,
                        help="HTTP timeout in seconds (default: 30)")
    parser.add_argument("--insecure", action="store_true",
                        help="skip TLS certificate verification (self-signed proxies)")
    args = parser.parse_args(argv)

    try:
        print(f"fetching {args.console_url}", file=sys.stderr)
        console_html = _fetch(args.console_url, args.insecure, args.timeout)
        print(f"fetching {args.models_url}", file=sys.stderr)
        models_raw = _fetch(args.models_url, args.insecure, args.timeout)
        api_models = json.loads(models_raw).get("data", [])
        model_ids = [m.get("id") for m in api_models if m.get("id")]
        rows = parse_console_rows(console_html)
    except Exception as exc:  # noqa: BLE001 - report and fail cleanly
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    existing = _load_existing(args.data)
    previous = {m.get("id"): m for m in existing.get("models", []) if m.get("id")}
    catalog = build_catalog(rows, api_models, previous)
    payload, new_ids = build(existing, catalog, model_ids, args.console_url, args.models_url)

    for mid in new_ids:
        print(f"new model id: {mid} (aa_status=no_data)", file=sys.stderr)
    print(
        f"parsed {len(payload['models'])} Go models "
        f"({len(new_ids)} new) - as of {payload['meta']['as_of']}",
        file=sys.stderr,
    )

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
