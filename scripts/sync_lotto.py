#!/usr/bin/env python3
"""Sync Taiwan Lottery Lotto 6/49 results to data/draws.json."""
from __future__ import annotations
import argparse
import json
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode
import requests

API = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result"
OUT = Path("data/draws.json")
START_YEAR = 2023
START_MONTH = 5

def month_iter(start_y, start_m, end_y, end_m):
    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1

def fetch_month(month):
    params = {"period": "", "month": month, "pageNum": 1, "pageSize": 50}
    url = API + "?" + urlencode(params)
    last_error = None
    for attempt in range(4):
        try:
            response = requests.get(url, timeout=25, headers={"User-Agent": "LOTTO-AI-history-sync/1.0"})
            response.raise_for_status()
            payload = response.json()
            content = payload.get("content")
            if not isinstance(content, dict) or "lotto649Res" not in content:
                raise RuntimeError("Unexpected response schema from lottery API")
            rows = content.get("lotto649Res") or []
            if not isinstance(rows, list):
                raise RuntimeError("Lottery API result is not a list")
            result = []
            for row in rows:
                raw = row.get("drawNumberSize")
                if isinstance(raw, list):
                    nums = [int(x) for x in raw]
                elif isinstance(raw, str):
                    parts = raw.replace(",", " ").split()
                    nums = [int(x) for x in parts] if parts else []
                else:
                    nums = []
                # API field contains six main numbers followed by the special number.
                if len(nums) < 7:
                    continue
                main, special = nums[:6], nums[6]
                if len(set(main)) != 6 or any(n < 1 or n > 49 for n in main) or not 1 <= special <= 49:
                    continue
                result.append({
                    "period": str(row.get("period", "")),
                    "date": str(row.get("lotteryDate", ""))[:10],
                    "numbers": sorted(main),
                    "special": special
                })
            if rows and not result:
                raise RuntimeError(f"{month}: API returned rows but no valid 6+1 number records")
            return result
        except Exception as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{month} API request failed: {last_error}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Fetch all available months from May 2023")
    args = parser.parse_args()
    today = date.today()
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {"draws": []}
    else:
        old = {"draws": []}
    by_period = {str(x["period"]): x for x in old.get("draws", []) if x.get("period")}
    if args.full or not by_period:
        months = list(month_iter(START_YEAR, START_MONTH, today.year, today.month))
    else:
        py, pm = today.year, today.month - 1
        if pm == 0:
            py, pm = py - 1, 12
        months = list(month_iter(py, pm, today.year, today.month))
    fetched = 0
    for month in months:
        rows = fetch_month(month)
        for row in rows:
            by_period[row["period"]] = row
            fetched += 1
        print(f"{month}: {len(rows)} draws")
        time.sleep(0.25)
    draws = sorted(by_period.values(), key=lambda x: (x.get("date", ""), x.get("period", "")))
    if not draws:
        raise RuntimeError("No valid draws received; refusing to overwrite data.")
    for draw in draws:
        assert len(draw["numbers"]) == 6 and len(set(draw["numbers"])) == 6
        assert all(1 <= n <= 49 for n in draw["numbers"])
        assert 1 <= draw["special"] <= 49
    OUT.parent.mkdir(exist_ok=True)
    payload = {
        "game": "大樂透",
        "source": "Taiwan Lottery website query API",
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "draw_count": len(draws),
        "draws": draws
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUT)
    print(f"Saved {len(draws)} draws; fetched rows: {fetched}")

if __name__ == "__main__":
    main()
