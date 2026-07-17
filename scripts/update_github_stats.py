#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

USERNAME = os.environ.get("GITHUB_USERNAME", "injisung0818-spec")
OUTPUT = Path("github-stats.svg")


def fetch_total_contributions(token: str, username: str) -> int:
    now = datetime.now(timezone.utc)
    variables = {
        "from": (now - timedelta(days=365)).isoformat(),
        "to": now.isoformat(),
    }
    query = (
        "query($from: DateTime!, $to: DateTime!) {"
        " viewer {"
        " login"
        " contributionsCollection(from: $from, to: $to) {"
        " contributionCalendar { totalContributions }"
        " }"
        " }"
        "}"
    )
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-stats-updater",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed: {exc.code} {message}") from exc

    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], ensure_ascii=False))

    viewer = payload["data"]["viewer"]
    if viewer["login"].lower() != username.lower():
        raise RuntimeError(
            f"PROFILE_STATS_TOKEN belongs to {viewer['login']}, not {username}. "
            "Use a token from the profile owner account."
        )
    return int(viewer["contributionsCollection"]["contributionCalendar"]["totalContributions"])


def build_svg(total: int) -> str:
    return f"""<svg width="551" height="258" viewBox="0 0 551 258" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">GitHub Stats</title>
  <desc id="desc">GitHub statistics with private contributions included: {total} total contributions.</desc>
  <rect x="0.5" y="0.5" width="550" height="257" rx="6" fill="#ffffff" stroke="#e5e7eb"/>
  <style>
    .label {{ fill: #374151; font: 800 27px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    .value {{ fill: #374151; font: 900 31px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    .icon {{ stroke: #2563eb; stroke-width: 3.5; stroke-linecap: round; stroke-linejoin: round; }}
  </style>
  <g transform="translate(32 34)">
    <path class="icon" d="m12 2 3.1 6.4 7 .9-5.1 5 1.2 7-6.2-3.3-6.2 3.3 1.2-7-5.1-5 7-.9L12 2Z"/>
    <text class="label" x="44" y="22">Total Stars Earned:</text>
    <text class="value" x="486" y="22" text-anchor="end">0</text>
  </g>
  <g transform="translate(32 78)">
    <path class="icon" d="M3 12a9 9 0 1 0 3-6.7M3 3v6h6"/>
    <path class="icon" d="M12 7v6l4 2"/>
    <text class="label" x="44" y="22">Total Commits:</text>
    <text class="value" x="486" y="22" text-anchor="end">{total}</text>
  </g>
  <g transform="translate(32 122)">
    <circle class="icon" cx="6" cy="5" r="3"/>
    <circle class="icon" cx="18" cy="19" r="3"/>
    <path class="icon" d="M6 8v6a5 5 0 0 0 5 5h4M18 16v-6a5 5 0 0 0-5-5h-2"/>
    <text class="label" x="44" y="22">Total PRs:</text>
    <text class="value" x="486" y="22" text-anchor="end">0</text>
  </g>
  <g transform="translate(32 166)">
    <circle class="icon" cx="12" cy="12" r="10"/>
    <path class="icon" d="M12 7v6M12 17h.01"/>
    <text class="label" x="44" y="22">Total Issues:</text>
    <text class="value" x="486" y="22" text-anchor="end">0</text>
  </g>
  <g transform="translate(32 210)">
    <path class="icon" d="M5 4h14v14H5zM8 22l4-3 4 3"/>
    <text class="label" x="44" y="22">Contributed to (last year):</text>
    <text class="value" x="486" y="22" text-anchor="end">0</text>
  </g>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, help="Use a fixed count instead of calling the GitHub API.")
    args = parser.parse_args()

    if args.count is not None:
        total = args.count
    else:
        token = os.environ.get("PROFILE_STATS_TOKEN") or os.environ.get("GITHUB_STATS_TOKEN")
        if not token:
            raise SystemExit("Set PROFILE_STATS_TOKEN to a token from the profile owner account.")
        total = fetch_total_contributions(token, USERNAME)

    svg = build_svg(total)
    OUTPUT.write_text(svg, encoding="utf-8")
    ElementTree.fromstring(svg)
    print(f"Updated {OUTPUT} with total={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
