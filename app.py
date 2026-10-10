from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Dict, Any

import pandas as pd
import requests


GITHUB_API = "https://api.github.com"


def safe_get_json(url: str, params: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None) -> Any:
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_github_events(username: str, max_events: int = 100) -> List[Dict[str, Any]]:
    events = []
    page = 1
    while len(events) < max_events:
        url = f"{GITHUB_API}/users/{username}/events/public"
        data = safe_get_json(url, params={"per_page": 100, "page": page})
        if not data:
            break
        for item in data:
            created_at = item.get("created_at")
            if not created_at:
                continue
            events.append({
                "date": created_at[:10],
                "datetime": created_at,
                "type": item.get("type", "unknown"),
                "repo": item.get("repo", {}).get("name", ""),
                "actor": item.get("actor", {}).get("login", username),
                "payload": item.get("payload", {}),
                "source": "github_activity",
            })
            if len(events) >= max_events:
                break
        if len(data) < 100:
            break
        page += 1
    return events


def fetch_github_releases(repo: str, max_releases: int = 20) -> List[Dict[str, Any]]:
    url = f"{GITHUB_API}/repos/{repo}/releases"
    data = safe_get_json(url, params={"per_page": max_releases})
    items = []
    for release in data:
        published = release.get("published_at") or release.get("created_at")
        if not published:
            continue
        items.append({
            "date": published[:10],
            "datetime": published,
            "name": release.get("name") or release.get("tag_name") or repo,
            "source": repo,
            "url": release.get("html_url"),
            "type": "release",
            "notes": release.get("body", "")[:500],
        })
    return items


def load_csv_timeline(path: str, source_name: str) -> List[Dict[str, Any]]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    rows = []
    with csv_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            date_val = row.get("date") or row.get("timestamp") or row.get("published_at") or row.get("released_at")
            if not date_val:
                continue
            rows.append({
                "date": date_val[:10] if isinstance(date_val, str) and len(date_val) >= 10 else date_val,
                "datetime": date_val,
                "name": row.get("name") or row.get("title") or row.get("product") or source_name,
                "source": row.get("source") or source_name,
                "url": row.get("url") or row.get("link") or "",
                "notes": row.get("notes") or row.get("summary") or row.get("description") or "",
                "type": row.get("type") or "custom",
            })
    return rows


def normalize_timeline(items: Iterable[Dict[str, Any]], default_type: str = "event") -> List[Dict[str, Any]]:
    normalized = []
    for item in items:
        date_str = str(item.get("date") or item.get("datetime") or "").strip()
        if not date_str:
            continue
        dt = date_str[:10] if len(date_str) >= 10 else date_str
        normalized.append({
            "date": dt,
            "datetime": item.get("datetime") or dt,
            "name": item.get("name") or item.get("title") or item.get("source") or item.get("repo") or "item",
            "source": item.get("source") or item.get("repo") or default_type,
            "url": item.get("url") or "",
            "notes": item.get("notes") or item.get("message") or "",
            "type": item.get("type") or default_type,
        })
    return normalized


def get_release_timeline(track_repos: List[str]) -> List[Dict[str, Any]]:
    all_items = []
    for repo in track_repos:
        repo = repo.strip().strip("/")
        if not repo:
            continue
        try:
            all_items.extend(fetch_github_releases(repo))
        except Exception as exc:
            print(f"Skipping {repo}: {exc}")
    return all_items


def make_summary(events: List[Dict[str, Any]], releases: List[Dict[str, Any]], news: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in events:
        rows.append({
            "date": item.get("date"),
            "name": item.get("repo") or item.get("actor") or item.get("name"),
            "kind": item.get("type"),
            "source": item.get("source"),
            "url": "",
            "notes": item.get("repo") or item.get("type"),
            "group": "github_activity",
        })
    for item in releases:
        rows.append({
            "date": item.get("date"),
            "name": item.get("name"),
            "kind": item.get("type") or "release",
            "source": item.get("source"),
            "url": item.get("url"),
            "notes": (item.get("notes") or "")[:300],
            "group": "release",
        })
    for item in news:
        rows.append({
            "date": item.get("date"),
            "name": item.get("name"),
            "kind": item.get("type") or "news",
            "source": item.get("source"),
            "url": item.get("url"),
            "notes": (item.get("notes") or "")[:300],
            "group": "news",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["date", "group"], ascending=[True, True], na_position="last")
    return df.reset_index(drop=True)


def build_html_report(df: pd.DataFrame, github_user: str) -> str:
    rows_html = ""
    for _, row in df.iterrows():
        notes = str(row.get("notes") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        url = row.get("url") or ""
        link_html = f'<a href="{url}" target="_blank">link</a>' if url else ""
        rows_html += (
            f"<tr><td>{row.get('date') or ''}</td><td>{row.get('group') or ''}</td>"
            f"<td>{str(row.get('name') or '').replace('&', '&amp;')}</td><td>{str(row.get('source') or '').replace('&', '&amp;')}</td>"
            f"<td>{notes}</td><td>{link_html}</td></tr>"
        )

    return f"""
    <html>
      <head>
        <meta charset="UTF-8" />
        <title>{github_user} activity versus products</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 32px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
            th {{ background: #f4f4f4; text-align: left; }}
            tr:nth-child(even) {{ background: #fafafa; }}
        </style>
      </head>
      <body>
        <h1>{github_user} activity vs. product timeline</h1>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Group</th>
              <th>Name</th>
              <th>Source</th>
              <th>Notes</th>
              <th>Link</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </body>
    </html>
    """


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare GitHub history with releases and news.")
    parser.add_argument("--github-user", required=True, help="GitHub username to inspect")
    parser.add_argument("--track-repos", default="", help="Comma-separated repos like owner/repo,owner/repo2")
    parser.add_argument("--release-csv", default="", help="Optional CSV with columns: date,name,source,url,notes,type")
    parser.add_argument("--news-csv", default="", help="Optional CSV with columns: date,name,source,url,notes,type")
    parser.add_argument("--max-events", type=int, default=200, help="Max GitHub events to fetch")
    parser.add_argument("--output-dir", default="output", help="Directory to write CSV and HTML outputs")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    events = fetch_github_events(args.github_user, max_events=args.max_events)
    releases = get_release_timeline([repo.strip() for repo in args.track_repos.split(",") if repo.strip()])

    if args.release_csv:
        releases.extend(load_csv_timeline(args.release_csv, "custom_release"))
    if args.news_csv:
        news = load_csv_timeline(args.news_csv, "custom_news")
    else:
        news = []

    combined = make_summary(events, releases, news)
    csv_path = output_dir / "timeline_summary.csv"
    html_path = output_dir / "timeline_report.html"

    if combined.empty:
        print("No data available to write.")
        return

    combined.to_csv(csv_path, index=False)
    html_path.write_text(build_html_report(combined, args.github_user), encoding="utf-8")

    print(f"Saved timeline CSV to {csv_path}")
    print(f"Saved HTML report to {html_path}")

    print("\nQuick summary:")
    print(f"GitHub events: {len(events)}")
    print(f"Releases tracked: {len(releases)}")
    print(f"News items: {len(news) if 'news' in locals() else 0}")

    by_group = combined.groupby('group').size().to_dict()
    print("Counts by category:", by_group)


if __name__ == "__main__":
    main()


































































































Mutation due to code continuation not needed.



































































































































































































































































































