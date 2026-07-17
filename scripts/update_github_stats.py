#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

USERNAME = os.environ.get("GITHUB_USERNAME", "injisung0818-spec")
OUTPUT = Path("github-stats.svg")


@dataclass
class GitHubStats:
    stars: int = 0
    contributions: int = 0
    prs: int = 0
    issues: int = 0
    contributed_to: int = 0


def github_request_json(url: str, token: str | None = None, data: bytes | None = None) -> dict:
    headers = {"User-Agent": "profile-readme-stats-updater"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub request failed: {exc.code} {message}") from exc


def fetch_graphql_stats(token: str, username: str) -> GitHubStats:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=365)
    repo_cursor: str | None = None
    stars = 0
    stats = GitHubStats()
    contributed_repos: set[str] = set()

    query = """
    query($from: DateTime!, $to: DateTime!, $repoCursor: String) {
      viewer {
        login
        repositories(first: 100, ownerAffiliations: OWNER, after: $repoCursor) {
          nodes { stargazerCount }
          pageInfo { hasNextPage endCursor }
        }
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
          totalIssueContributions
          totalPullRequestContributions
          commitContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner } }
          issueContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner } }
          pullRequestContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner } }
          pullRequestReviewContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner } }
        }
      }
    }
    """

    while True:
        payload = github_request_json(
            "https://api.github.com/graphql",
            token=token,
            data=json.dumps(
                {
                    "query": query,
                    "variables": {
                        "from": since.isoformat(),
                        "to": now.isoformat(),
                        "repoCursor": repo_cursor,
                    },
                }
            ).encode("utf-8"),
        )
        if payload.get("errors"):
            raise RuntimeError(json.dumps(payload["errors"], ensure_ascii=False))

        viewer = payload["data"]["viewer"]
        if viewer["login"].lower() != username.lower():
            raise RuntimeError(
                f"PROFILE_STATS_TOKEN belongs to {viewer['login']}, not {username}. "
                "Use a token from the profile owner account."
            )

        repositories = viewer["repositories"]
        stars += sum(repo["stargazerCount"] for repo in repositories["nodes"])

        collection = viewer["contributionsCollection"]
        stats.contributions = int(collection["contributionCalendar"]["totalContributions"])
        stats.issues = int(collection["totalIssueContributions"])
        stats.prs = int(collection["totalPullRequestContributions"])
        for field in (
            "commitContributionsByRepository",
            "issueContributionsByRepository",
            "pullRequestContributionsByRepository",
            "pullRequestReviewContributionsByRepository",
        ):
            for item in collection[field]:
                contributed_repos.add(item["repository"]["nameWithOwner"])

        page_info = repositories["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        repo_cursor = page_info["endCursor"]

    stats.stars = stars
    stats.contributed_to = len(contributed_repos)
    return stats


def fetch_public_profile_total(username: str) -> int:
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=365)
    query = urllib.parse.urlencode({"from": since.isoformat(), "to": today.isoformat()})
    request = urllib.request.Request(
        f"https://github.com/users/{username}/contributions?{query}",
        headers={"User-Agent": "profile-readme-stats-updater"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    match = re.search(r'([0-9][0-9,]*)\s+contributions\s+in', html, re.I)
    if not match:
        raise RuntimeError("Could not find the public contribution total on GitHub's contributions endpoint.")
    return int(match.group(1).replace(",", ""))


def fetch_public_repo_stars(username: str) -> int:
    stars = 0
    page = 1
    while True:
        url = f"https://api.github.com/users/{username}/repos?type=owner&per_page=100&page={page}"
        repos = github_request_json(url)
        if not repos:
            break
        stars += sum(int(repo.get("stargazers_count", 0)) for repo in repos)
        page += 1
    return stars


def fetch_public_search_count(query: str) -> int:
    encoded = urllib.parse.urlencode({"q": query, "per_page": "1"})
    payload = github_request_json(f"https://api.github.com/search/issues?{encoded}")
    return int(payload.get("total_count", 0))


def fetch_public_stats(username: str) -> GitHubStats:
    since = (datetime.now(timezone.utc) - timedelta(days=365)).date().isoformat()
    return GitHubStats(
        stars=fetch_public_repo_stars(username),
        contributions=fetch_public_profile_total(username),
        prs=fetch_public_search_count(f"author:{username} type:pr created:>={since}"),
        issues=fetch_public_search_count(f"author:{username} type:issue created:>={since}"),
        contributed_to=0,
    )


def build_svg(stats: GitHubStats) -> str:
    return f"""<svg width="551" height="258" viewBox="0 0 551 258" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">GitHub Stats</title>
  <desc id="desc">GitHub statistics: {stats.contributions} total contributions, {stats.stars} stars, {stats.prs} pull requests, {stats.issues} issues.</desc>
  <rect x="0.5" y="0.5" width="550" height="257" rx="6" fill="#ffffff" stroke="#e5e7eb"/>
  <style>
    .label {{ fill: #374151; font: 800 27px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    .value {{ fill: #374151; font: 900 31px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    .icon {{ stroke: #2563eb; stroke-width: 3.5; stroke-linecap: round; stroke-linejoin: round; }}
  </style>
  <g transform="translate(32 34)">
    <path class="icon" d="m12 2 3.1 6.4 7 .9-5.1 5 1.2 7-6.2-3.3-6.2 3.3 1.2-7-5.1-5 7-.9L12 2Z"/>
    <text class="label" x="44" y="22">Total Stars Earned:</text>
    <text class="value" x="486" y="22" text-anchor="end">{stats.stars}</text>
  </g>
  <g transform="translate(32 78)">
    <path class="icon" d="M3 12a9 9 0 1 0 3-6.7M3 3v6h6"/>
    <path class="icon" d="M12 7v6l4 2"/>
    <text class="label" x="44" y="22">Total Contributions:</text>
    <text class="value" x="486" y="22" text-anchor="end">{stats.contributions}</text>
  </g>
  <g transform="translate(32 122)">
    <circle class="icon" cx="6" cy="5" r="3"/>
    <circle class="icon" cx="18" cy="19" r="3"/>
    <path class="icon" d="M6 8v6a5 5 0 0 0 5 5h4M18 16v-6a5 5 0 0 0-5-5h-2"/>
    <text class="label" x="44" y="22">Total PRs:</text>
    <text class="value" x="486" y="22" text-anchor="end">{stats.prs}</text>
  </g>
  <g transform="translate(32 166)">
    <circle class="icon" cx="12" cy="12" r="10"/>
    <path class="icon" d="M12 7v6M12 17h.01"/>
    <text class="label" x="44" y="22">Total Issues:</text>
    <text class="value" x="486" y="22" text-anchor="end">{stats.issues}</text>
  </g>
  <g transform="translate(32 210)">
    <path class="icon" d="M5 4h14v14H5zM8 22l4-3 4 3"/>
    <text class="label" x="44" y="22">Contributed to (last year):</text>
    <text class="value" x="486" y="22" text-anchor="end">{stats.contributed_to}</text>
  </g>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, help="Use a fixed contribution count instead of calling GitHub.")
    parser.add_argument("--stars", type=int, default=0)
    parser.add_argument("--prs", type=int, default=0)
    parser.add_argument("--issues", type=int, default=0)
    parser.add_argument("--contributed-to", type=int, default=0)
    args = parser.parse_args()

    if args.count is not None:
        stats = GitHubStats(
            stars=args.stars,
            contributions=args.count,
            prs=args.prs,
            issues=args.issues,
            contributed_to=args.contributed_to,
        )
    else:
        token = os.environ.get("PROFILE_STATS_TOKEN") or os.environ.get("GITHUB_STATS_TOKEN")
        stats = fetch_graphql_stats(token, USERNAME) if token else fetch_public_stats(USERNAME)

    svg = build_svg(stats)
    OUTPUT.write_text(svg, encoding="utf-8")
    ElementTree.fromstring(svg)
    print(
        "Updated {output} with stars={stars}, contributions={contributions}, "
        "prs={prs}, issues={issues}, contributed_to={contributed_to}".format(
            output=OUTPUT,
            stars=stats.stars,
            contributions=stats.contributions,
            prs=stats.prs,
            issues=stats.issues,
            contributed_to=stats.contributed_to,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
