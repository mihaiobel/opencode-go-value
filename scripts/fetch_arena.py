#!/usr/bin/env python3
"""Refresh the LMArena Overall values in data/latest.json and print the result on stdout.

Source: the public Hugging Face mirror of the LMArena leaderboard
(lmarena-ai/leaderboard-dataset, config "text", split "latest", category "overall").
The leaderboard site itself blocks scripted access, the mirror is updated daily.

Needs pyarrow to read the parquet file (``pip install pyarrow``).

Matching
--------
1. data/arena_map.json maps a Go model id to the Arena model_name -> bench2_status "mapped".
2. Otherwise an Arena entry whose name equals the id counts -> bench2_status "ok".
3. Otherwise the value is null and bench2_status is "missing". Nothing is guessed.

Example
-------
    python3 scripts/fetch_arena.py --data data/latest.json > /tmp/latest.json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request

PARQUET_URL = (
    "https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset"
    "/resolve/main/text/latest-00000-of-00001.parquet"
)
USER_AGENT = "opencode-go-value/1.0 (+https://github.com/mihaiobel/opencode-go-value)"
FORMULA = (
    "score = mean over available sources of 100*(x-min)/(max-min); min and max are "
    "the lowest and highest value of that source among the listed models; "
    "a missing source is skipped and flagged."
)


def fetch_overall(url: str, timeout: int) -> tuple[dict[str, float], str]:
    import pyarrow.parquet as pq  # imported late so --help works without it

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    rows = pq.read_table(io.BytesIO(raw), columns=["model_name", "rating", "category", "leaderboard_publish_date"]).to_pylist()
    overall = [r for r in rows if r["category"] == "overall" and r["rating"] is not None]
    if not overall:
        raise ValueError("no 'overall' rows in the leaderboard file")
    published = max(str(r["leaderboard_publish_date"]) for r in overall)
    return {r["model_name"]: float(r["rating"]) for r in overall}, published


def apply(existing: dict, ratings: dict[str, float], mapping: dict[str, str], published: str) -> dict:
    models = []
    for m in existing.get("models", []):
        m = dict(m)
        mid = m["id"]
        mapped = mapping.get(mid)
        if mapped is not None and mapped in ratings:
            m["bench2_score"] = round(ratings[mapped], 2)
            m["bench2_status"] = "mapped"
        elif mapped is None and mid in ratings:
            m["bench2_score"] = round(ratings[mid], 2)
            m["bench2_status"] = "ok"
        else:
            if mapped is not None:
                print(f"warning: {mid}: Arena entry {mapped!r} not found", file=sys.stderr)
            m["bench2_score"] = None
            m["bench2_status"] = "missing"
        models.append(m)
    meta = dict(existing.get("meta", {}))
    meta["bench2_stand"] = published
    meta["bench2_formel"] = FORMULA
    return {"meta": meta, "models": models}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fetch_arena.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data/latest.json")
    parser.add_argument("--map", default="data/arena_map.json")
    parser.add_argument("--url", default=PARQUET_URL)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv)

    try:
        with open(args.data, encoding="utf-8") as fh:
            existing = json.load(fh)
        with open(args.map, encoding="utf-8") as fh:
            mapping = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
        print(f"fetching {args.url}", file=sys.stderr)
        ratings, published = fetch_overall(args.url, args.timeout)
    except Exception as exc:  # noqa: BLE001 - report and fail cleanly
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    payload = apply(existing, ratings, mapping, published)
    counts: dict[str, int] = {}
    for m in payload["models"]:
        counts[m["bench2_status"]] = counts.get(m["bench2_status"], 0) + 1
    print(f"arena stand {published}: {counts}", file=sys.stderr)
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
