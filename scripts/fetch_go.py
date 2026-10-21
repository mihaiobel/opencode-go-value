#!/usr/bin/env python3
"""Fetch the opencode Go plan catalog and emit an updated data/latest.json on stdout.

Only the standard library is used (urllib, re, json, ...).

What it does
------------
1. Downloads https://opencode.ai/docs/go/ and https://opencode.ai/inference/go/v1/models.
2. Parses the **Go plan** tables (``data-plan-panel="go"``) only -- the Go Plus tab
   (``data-plan-panel="go-plus"``) is ignored on purpose.
3. Carries the Artificial Analysis values (aa_intelligence, aa_speed_tps,
   aa_cost_per_task, aa_status) over from the existing ``data/latest.json`` by model id.
   ``meta.featured_ids`` (the models opencode.ai/go lists by default) is kept as is.
4. Detects new model ids by diffing against the existing file. New models get
   ``aa_status: "no_data"`` and null AA fields (benchmarks are never guessed).
5. Prints the updated JSON to stdout. Diagnostics go to stderr, so stdout stays
   valid JSON and can be redirected straight into ``data/latest.json``.

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

DOCS_URL = "https://opencode.ai/docs/go/"
MODELS_URL = "https://opencode.ai/inference/go/v1/models"
USER_AGENT = "opencode-go-value/1.0 (+https://opencode.ai/docs/go/)"

FREE_REASON = (
    "Free nur befristet (limited time); kein eigener AA-Slug, keine Benchmark-Daten"
)


def _fetch(url: str, insecure: bool = False, timeout: int = 30) -> str:
    """Fetch *url* and return the decoded body."""
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
    """Turn an HTML cell into plain text."""
    cell = re.sub(r"(?is)<small\b.*?</small>", " ", cell)
    cell = re.sub(r"(?i)<br\s*/?>", " ", cell)
    cell = re.sub(r"<[^>]+>", "", cell)
    cell = unescape(cell)
    return re.sub(r"\s+", " ", cell).strip()


def _parse_table(table_html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", table_html):
        cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)
        rows.append([_strip_tags(c) for c in cells])
    return rows


def _go_tables(html: str) -> list[list[list[str]]]:
    """Return the parsed tables inside every ``data-plan-panel="go"`` block."""
    tables: list[list[list[str]]] = []
    for match in re.finditer(r'data-plan-panel="go"', html):
        start = html.find("<table", match.end())
        if start == -1:
            continue
        end = html.find("</table>", start)
        if end == -1:
            continue
        tables.append(_parse_table(html[start : end + len("</table>")]))
    return tables


def _num(text: str):
    """Parse a currency/number cell into a float, or None when not numeric."""
    if text is None:
        return None
    cleaned = text.replace(",", "").replace("$", "").strip()
    if cleaned == "" or cleaned.lower().startswith("unlimited") or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _find_table(tables, header_key: str):
    for rows in tables:
        if rows and any(header_key.lower() in c.lower() for c in rows[0]):
            return rows
    return None


def _endpoint_map(html: str) -> dict[str, str]:
    """Map display name -> model id from the non-plan 'Model ID' endpoint table."""
    mapping: dict[str, str] = {}
    for tbl in re.findall(r"(?is)<table[^>]*>.*?</table>", html):
        rows = _parse_table(tbl)
        if not rows or not any("model id" in c.lower() for c in rows[0]):
            continue
        for cells in rows[1:]:
            if len(cells) >= 2 and cells[1]:
                mapping[cells[0].strip()] = cells[1].strip()
        break
    return mapping


def _slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"\s+", "-", s.strip())
    return re.sub(r"[^a-z0-9.\-]", "", s)


def _base_name(name: str) -> str:
    """Drop tiering qualifiers, e.g. 'Qwen3.7 Plus (<= 256K tokens)' -> 'Qwen3.7 Plus'."""
    return re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()


def parse_go_catalog(html: str) -> dict[str, dict]:
    """Parse the Go pricing + request tables into a model catalog keyed by id."""
    tables = _go_tables(html)
    pricing = _find_table(tables, "Monthly limit")
    requests = _find_table(tables, "Requests per 5 hours")
    if pricing is None:
        raise ValueError("Go pricing table (Monthly limit) not found in docs page")

    endpoints = _endpoint_map(html)

    # name -> req/5h (None = Unlimited); keyed by base name
    req_by_name: dict[str, float] = {}
    if requests is not None:
        for cells in requests[1:]:
            if len(cells) >= 2:
                req_by_name[_base_name(cells[0])] = _num(cells[1])

    catalog: dict[str, dict] = {}
    for cells in pricing[1:]:
        if len(cells) < 6:
            continue
        base = _base_name(cells[0])
        if not base:
            continue
        # Tiered rows (DeepSeek peak/off-peak, context tiers, ...) collapse onto one
        # base id; the first listed tier (the base/cheapest one) wins.
        model_id = endpoints.get(base) or _slug(base)
        if model_id in catalog:
            continue
        free = "free" in base.lower() or model_id.endswith("-free")
        catalog[model_id] = {
            "id": model_id,
            "name": base,
            "monthly_limit_usd": _num(cells[5]),
            "requests_per_5h": req_by_name.get(base),
            "price_in": 0.0 if free else _num(cells[1]),
            "price_out": 0.0 if free else _num(cells[2]),
            "price_cached": 0.0 if free else _num(cells[3]),
            "free": free,
        }
    if not catalog:
        raise ValueError("Go pricing table contained no model rows")
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


def build(existing: dict, catalog: dict, model_ids: list[str], docs_url: str,
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
    meta["stand_datum"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    meta.setdefault("aa_index_version", "Artificial Analysis Intelligence Index v4.3.2")
    meta.setdefault("plan", "opencode-go ($10/month)")
    meta.setdefault("quellen_urls", [docs_url, models_url])
    if new_ids:
        meta["new_models"] = new_ids
    else:
        meta.pop("new_models", None)
    # ids the models endpoint knows but the docs pricing table does not list
    undocumented = sorted(set(model_ids) - set(catalog))
    if undocumented:
        meta["undocumented_ids"] = undocumented

    return {"meta": meta, "models": models}, new_ids


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="fetch_go.py",
        description=(
            "Fetch the opencode Go plan tables (Go, not Go Plus), carry over the "
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
    parser.add_argument("--docs-url", default=DOCS_URL,
                        help=f"docs page with the Go tables (default: {DOCS_URL})")
    parser.add_argument("--models-url", default=MODELS_URL,
                        help=f"models endpoint (default: {MODELS_URL})")
    parser.add_argument("--timeout", type=int, default=30,
                        help="HTTP timeout in seconds (default: 30)")
    parser.add_argument("--insecure", action="store_true",
                        help="skip TLS certificate verification (self-signed proxies)")
    args = parser.parse_args(argv)

    try:
        print(f"fetching {args.docs_url}", file=sys.stderr)
        docs_html = _fetch(args.docs_url, args.insecure, args.timeout)
        print(f"fetching {args.models_url}", file=sys.stderr)
        models_raw = _fetch(args.models_url, args.insecure, args.timeout)
        model_ids = [m.get("id") for m in json.loads(models_raw).get("data", []) if m.get("id")]
        catalog = parse_go_catalog(docs_html)
    except Exception as exc:  # noqa: BLE001 - report and fail cleanly
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    existing = _load_existing(args.data)
    payload, new_ids = build(existing, catalog, model_ids, args.docs_url, args.models_url)

    for mid in new_ids:
        print(f"new model id: {mid} (aa_status=no_data)", file=sys.stderr)
    print(
        f"parsed {len(payload['models'])} Go models "
        f"({len(new_ids)} new) - stand {payload['meta']['stand_datum']}",
        file=sys.stderr,
    )

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
