#!/usr/bin/env python3
"""Audit every opencode Go model id in data/latest.json against Artificial Analysis.

Standard library only (urllib, json, re, sys).

For each model id it tries, in order (stopping at the first 200):

1. https://artificialanalysis.ai/models/<go-id>                        -> exakt
2. https://artificialanalysis.ai/models/releases/<dashed-go-id>        -> mapped
3. if the id ends in -contributor: the release URL of the id with that
   suffix stripped (dots dashed, because AA slugs are dashed)          -> mapped
4. if the id ends in -preview-free: https://artificialanalysis.ai/models/<base>
   with the suffix stripped (dots dashed)                              -> mapped

There is deliberately no -max / -pro fallback: that guessed wrong models.
When nothing hits, the id is reported as 404 plus a hint line naming the
candidates that were tried.

From a 200 page the model-summary block is scraped with a regex:
Intelligence Index, output speed (tokens/s) and cost per intelligence task.

One request per second, 30s timeout, User-Agent opencode-go-value-audit/1.0.
Prints one line per model to stdout and a summary at the end; progress goes to
stderr. Nothing in the repo is written.

    python3 scripts/audit_aa.py > /tmp/aa-audit.txt
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request

USER_AGENT = "opencode-go-value-audit/1.0"
MODELS_URL = "https://artificialanalysis.ai/models/"
DELAY = 1.0
TIMEOUT = 30
DATA = "data/latest.json"

L_INTEL = "Artificial Analysis Intelligence Index"
L_SPEED = "Output tokens per second"
L_COST = "Cost per Intelligence Index task"

_LAST_REQUEST = 0.0


def get(url: str) -> tuple[int | None, str | None]:
    """Throttled GET. Return (status, body); status None on network error."""
    global _LAST_REQUEST
    wait = DELAY - (time.monotonic() - _LAST_REQUEST)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            _LAST_REQUEST = time.monotonic()
            return resp.status, body
    except urllib.error.HTTPError as exc:
        _LAST_REQUEST = time.monotonic()
        return exc.code, None
    except Exception as exc:  # noqa: BLE001 - network trouble: report, keep going
        _LAST_REQUEST = time.monotonic()
        print(f"  warn: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None, None


def _value(html: str, label: str) -> str | None:
    """Scrape the summary value for *label*.

    In the rendered page the value sits in a <span> just before the label div;
    a label-then-value layout is tried as a fallback.
    """
    before = re.search(
        r"<span[^>]*>([^<]{1,24})</span>\s*</div>\s*<div[^>]*>\s*" + re.escape(label),
        html,
        re.I,
    )
    if before:
        return before.group(1).strip()
    after = re.search(
        re.escape(label) + r"</div>\s*(?:<[^>]+>\s*)*?<span[^>]*>([^<]{1,24})</span>",
        html,
        re.I,
    )
    if after:
        return after.group(1).strip()
    return None


def _clean_number(raw: str | None) -> str | None:
    if raw is None:
        return None
    return raw.replace("$", "").replace(",", "").strip()


def extract(html: str) -> tuple[str | None, str | None, str | None]:
    return (
        _clean_number(_value(html, L_INTEL)),
        _clean_number(_value(html, L_SPEED)),
        _clean_number(_value(html, L_COST)),
    )


def candidates(model_id: str) -> list[tuple[str, str]]:
    """Return the ordered (url, kind) candidates for *model_id*.

    AA slugs are dashed, so dots become dashes. Two Go-only suffixes are
    handled explicitly: -contributor is stripped and looked up as a release,
    -preview-free falls back to its base model page.
    """
    dashed = model_id.replace(".", "-")

    out: list[tuple[str, str]] = [(MODELS_URL + model_id, "exakt")]
    out.append((MODELS_URL + "releases/" + dashed, "mapped"))
    if model_id.endswith("-contributor"):
        stripped = model_id[: -len("-contributor")].replace(".", "-")
        out.append((MODELS_URL + "releases/" + stripped, "mapped"))
    if model_id.endswith("-preview-free"):
        base = model_id[: -len("-preview-free")].replace(".", "-")
        out.append((MODELS_URL + base, "mapped"))
    return out


def audit(model_id: str):
    """Return (id, url, intel, speed, cost, kind) for the first candidate that hits."""
    cands = candidates(model_id)
    for url, kind in cands:
        status, body = get(url)
        if status == 200:
            intel, speed, cost = extract(body or "")
            return model_id, url, intel, speed, cost, kind
        if status is not None:
            print(f"  {status} {url}", file=sys.stderr)
    tried = ", ".join(url.removeprefix(MODELS_URL) for url, _ in cands)
    print(f"    404 {model_id}: no AA page found (tried: {tried})")
    return model_id, None, None, None, None, "404"


def main(argv=None) -> int:
    path = argv[0] if argv else DATA
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 1

    model_ids = [m.get("id") for m in data.get("models", []) if m.get("id")]

    print(f"{'ID':<30} | {'URL':<58} | {'Intel':>5} | {'Speed':>7} | {'Cost':>6} | Kind")
    print("-" * 130)

    counts = {"exakt": 0, "mapped": 0, "404": 0}
    for model_id in model_ids:
        mid, url, intel, speed, cost, kind = audit(model_id)
        counts[kind] = counts.get(kind, 0) + 1
        print(
            f"{mid:<30} | {url or '-':<58} | {intel or '-':>5} | "
            f"{speed or '-':>7} | {cost or '-':>6} | {kind}"
        )

    print("-" * 130)
    print(
        f"summary: {counts['exakt']} exakt, {counts['mapped']} mapped, "
        f"{counts['404']} 404 (total {len(model_ids)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
