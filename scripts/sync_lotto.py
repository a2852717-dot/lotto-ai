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
START_YEAR = 2007
START_MONTH = 1
PAGE_SIZE = 200


def month_iter(start_y: int, start_m: int, end_y: int, end_m: int):
    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def parse_row(row: dict, month_range: str) -> dict:
    raw = row.get("drawNumberSize")
    if isinstance(raw, list):
        nums = [int(x) for x in raw]
    elif isinstance(raw, str):
        parts = raw.replace(",", " ").split()
        nums = [int(x) for x in parts] if parts else []
    else:
        nums = []

    period = str(row.get("period", "")).strip()
    draw_date = str(row.get("lotteryDate", ""))[:10]
    if len(nums) != 7:
        raise RuntimeError(f"{month_range}: {period} has invalid drawNumberSize: {raw!r}")
    main, special = nums[:6], nums[6]
    if len(set(main)) != 6 or any(n < 1 or n > 49 for n in main):
        raise RuntimeError(f"{month_range}: {period} has invalid main numbers: {main}")
    if not 1 <= special <= 49:
        raise RuntimeError(f"{month_range}: {period} has invalid special number: {special}")
    try:
        datetime.strptime(draw_date, "%Y-%m-%d")
    except ValueError as exc:
        raise RuntimeError(f"{month_range}: {period} has invalid lottery date: {draw_date!r}") from exc
    if not period:
        raise RuntimeError(f"{month_range}: result is missing its period")

    return {
        "period": period,
        "date": draw_date,
        "numbers": sorted(main),
        "special": special,
    }


def fetch_range(start_month: str, end_month: str) -> list[dict]:
    """Fetch every result in an inclusive month range, following API pagination."""
    page = 1
    total_size = None
    result = []
    last_error = None

    while total_size is None or len(result) < total_size:
        params = {
            "month": start_month,
            "endMonth": end_month,
            "pageNum": page,
            "pageSize": PAGE_SIZE,
        }
        url = API + "?" + urlencode(params)
        payload = None
        for attempt in range(4):
            try:
                response = requests.get(
                    url,
                    timeout=30,
                    headers={"User-Agent": "LOTTO-AI-history-sync/2.0"},
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("rtCode") not in (None, 0, "0"):
                    raise RuntimeError(f"Lottery API returned rtCode={payload.get('rtCode')}")
                break
            except Exception as exc:
                last_error = exc
                if attempt == 3:
                    raise RuntimeError(
                        f"{start_month} to {end_month} API request failed: {last_error}"
                    ) from exc
                time.sleep(2 ** attempt)

        content = payload.get("content") if isinstance(payload, dict) else None
        if not isinstance(content, dict):
            raise RuntimeError(f"{start_month} to {end_month}: unexpected API response")
        rows = content.get("lotto649Res")
        if not isinstance(rows, list):
            raise RuntimeError(f"{start_month} to {end_month}: missing lotto649Res list")
        page_total = content.get("totalSize")
        if not isinstance(page_total, int):
            raise RuntimeError(f"{start_month} to {end_month}: missing/invalid totalSize")
        if total_size is None:
            total_size = page_total
        elif page_total != total_size:
            raise RuntimeError(f"{start_month} to {end_month}: totalSize changed during pagination")

        for row in rows:
            if not isinstance(row, dict):
                raise RuntimeError(f"{start_month} to {end_month}: malformed result row")
            result.append(parse_row(row, f"{start_month} to {end_month}"))

        print(f"{start_month} to {end_month}, page {page}: {len(rows)} / {total_size}")
        if not rows:
            break
        page += 1
        time.sleep(0.15)

    if len(result) != (total_size or 0):
        raise RuntimeError(
            f"{start_month} to {end_month}: expected {total_size} rows, received {len(result)}"
        )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Backfill all available Lotto 6/49 results from January 2007",
    )
    args = parser.parse_args()
    today = date.today()

    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Cannot read existing {OUT}; refusing to overwrite it") from exc
    else:
        old = {"draws": []}

    by_period = {
        str(item["period"]): item
        for item in old.get("draws", [])
        if isinstance(item, dict) and item.get("period")
    }

    if args.full or not by_period:
        ranges = [
            (f"{year:04d}-01", f"{year:04d}-12" if year < today.year else f"{today.year:04d}-{today.month:02d}")
            for year in range(START_YEAR, today.year + 1)
        ]
    else:
        previous_year, previous_month = today.year, today.month - 1
        if previous_month == 0:
            previous_year, previous_month = today.year - 1, 12
        ranges = [(f"{previous_year:04d}-{previous_month:02d}", f"{today.year:04d}-{today.month:02d}")]

    fetched = 0
    for start_month, end_month in ranges:
        rows = fetch_range(start_month, end_month)
        for row in rows:
            by_period[row["period"]] = row
            fetched += 1

    draws = sorted(by_period.values(), key=lambda item: (item.get("date", ""), item.get("period", "")))
    if not draws:
        raise RuntimeError("No valid draws received; refusing to overwrite data.")

    seen_periods = set()
    for draw in draws:
        period = str(draw["period"])
        if period in seen_periods:
            raise RuntimeError(f"Duplicate draw period detected: {period}")
        seen_periods.add(period)
        if len(draw["numbers"]) != 6 or len(set(draw["numbers"])) != 6:
            raise RuntimeError(f"{period}: expected six unique main numbers")
        if any(not 1 <= int(number) <= 49 for number in draw["numbers"]):
            raise RuntimeError(f"{period}: main number outside 1-49")
        if not 1 <= int(draw["special"]) <= 49:
            raise RuntimeError(f"{period}: special number outside 1-49")

    OUT.parent.mkdir(exist_ok=True)
    payload = {
        "game": "大樂透",
        "source": "Taiwan Lottery official query API (historical monthly range)",
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "draw_count": len(draws),
        "draws": draws,
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUT)
    print(f"Saved {len(draws)} unique draws; fetched rows: {fetched}")
    print(f"Coverage: {draws[0]['date']} to {draws[-1]['date']}")
    print(f"First period: {draws[0]['period']}; latest period: {draws[-1]['period']}")


if __name__ == "__main__":
    main()
