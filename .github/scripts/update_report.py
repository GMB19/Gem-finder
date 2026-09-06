#!/usr/bin/env python3
"""Weekly auto-updater for the Gem-finder report.

Pulls a fixed set of public RSS feeds, filters them for NFL / fantasy-football
relevance, and rewrites the "Auto-Refreshed News" section of
`2026-fantasy-gems.md` in place. It also appends a dated snapshot to
`news-archive.md` so each Wednesday's digest is preserved.

Designed to run from GitHub Actions on a cron schedule (see
`.github/workflows/update-gems.yml`). All sources are public and keyless.
"""

import re
import sys
import time
from datetime import date, timedelta

import feedparser
import requests

REPORT = "2026-fantasy-gems.md"
ARCHIVE = "news-archive.md"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# label -> public RSS URL. Add/remove sources here freely.
FEEDS = [
    ("RotoBaller (fantasy)", "https://www.rotoballer.com/feed"),
    ("FantasyPros (fantasy)", "https://www.fantasypros.com/feed/"),
    ("ESPN (NFL)", "https://www.espn.com/espn/rss/nfl/news"),
    ("ProFootballTalk (NFL)", "https://profootballtalk.nbcsports.com/feed/"),
]

PER_FEED = 8          # max headlines kept per source, per refresh
ARCHIVE_WEEKS = 14    # how many weekly snapshots to keep in news-archive.md

# Off-topic sports to drop outright.
NON_FOOTBALL = re.compile(
    r"\b(mlb|baseball|nba|basketball|nhl|hockey|golf|tennis|mma|ufc|boxing|"
    r"soccer|premier league|la liga|serie a|bundesliga|wnba|ncaa basketball)\b",
    re.IGNORECASE,
)
# College football is noise unless it is NFL-draft adjacent.
COLLEGE = re.compile(r"\b(college football|ncaaf?)\b", re.IGNORECASE)
DRAFT_ADJACENT = re.compile(r"\b(nfl|draft|prospect)\b", re.IGNORECASE)

# These terms bump an item higher in its source's ordering.
FANTASY_TERMS = re.compile(
    r"\b(fantasy|sleeper|breakout|waiver|rankings?|draft|adp|depth chart|"
    r"injury|start/sit|start 'em|sit 'em|league.winner|league-winner|"
    r"target share|touchdown|extension|contract|signing|trade|released|cut|"
    r"practice squad|53-man|roster)\b",
    re.IGNORECASE,
)


def fetch_items():
    """Return (rows, errors) where rows is [(label, [(pub, title, link), ...])]."""
    rows, errors = [], []
    for label, url in FEEDS:
        try:
            resp = requests.get(url, timeout=25, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            items = []
            for entry in feed.entries:
                title = (entry.get("title") or "").strip()
                link = (entry.get("link") or "").strip()
                if not title or not link:
                    continue
                if NON_FOOTBALL.search(title):
                    continue
                if COLLEGE.search(title) and not DRAFT_ADJACENT.search(title):
                    continue
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                pub = time.strftime("%Y-%m-%d", published) if published else ""
                score = 2 if FANTASY_TERMS.search(title) else 0
                items.append((score, pub, title, link))
            items.sort(key=lambda x: (x[0], x[1]), reverse=True)
            rows.append((label, items[:PER_FEED]))
        except Exception as exc:  # keep going if one source is down
            errors.append(f"{label} ({exc.__class__.__name__})")
    return rows, errors


def render(rows, errors):
    """Render the digest as markdown bullet lists grouped by source."""
    blocks = []
    for label, items in rows:
        if not items:
            blocks.append(f"**{label}** — no matching items this week.")
            continue
        lines = [f"**{label}**"]
        for _score, pub, title, link in items:
            stamp = f" ({pub})" if pub else ""
            lines.append(f"- [{title}]({link}){stamp}")
        blocks.append("\n".join(lines))
    body = "\n\n".join(blocks)
    if errors:
        body += "\n\n> ⚠️ Could not fetch this week: " + ", ".join(errors)
    return body


def update_report(news_md, last_refresh, next_refresh):
    """Rewrite the auto-news block and refresh stamps inside the report."""
    start, end = "<!-- AUTO-NEWS-START -->", "<!-- AUTO-NEWS-END -->"
    with open(REPORT, encoding="utf-8") as fh:
        text = fh.read()
    if start not in text or end not in text:
        print(f"ERROR: markers {start} / {end} not found in {REPORT}", file=sys.stderr)
        return False

    block = f"{start}\n{news_md}\n{end}"
    text = re.sub(
        rf"{re.escape(start)}.*?{re.escape(end)}", block, text, count=1, flags=re.S
    )
    text = re.sub(
        r"\*\*Last auto-refresh:\*\*[^*]*",
        f"**Last auto-refresh:** {last_refresh} · ",
        text,
        count=1,
    )
    text = re.sub(
        r"\*\*Next auto-refresh:\*\*[^*]*",
        f"**Next auto-refresh:** {next_refresh} · ",
        text,
        count=1,
    )
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write(text)
    return True


def update_archive(news_md, today):
    """Prepend a dated weekly snapshot to news-archive.md, pruning old ones."""
    heading = f"## {today} — weekly auto-refresh"
    new_section = f"{heading}\n\n{news_md}"
    try:
        with open(ARCHIVE, encoding="utf-8") as fh:
            old = fh.read()
    except FileNotFoundError:
        old = ""

    sections = [s.strip() for s in re.split(r"(?m)^(?=##\s)", old) if s.strip()]
    sections = [s for s in sections if not s.startswith("# News Archive")]
    sections = [new_section] + sections
    sections = sections[:ARCHIVE_WEEKS]

    with open(ARCHIVE, "w", encoding="utf-8") as fh:
        fh.write("# News Archive (auto)\n\n" + "\n\n".join(sections) + "\n")


def main():
    rows, errors = fetch_items()
    total = sum(len(items) for _, items in rows)

    if total == 0:
        news_md = (
            "> ⚠️ No feeds could be fetched this week, so there are no headlines "
            "to show. The refresh stamp below was still updated so the failure is "
            "visible."
        )
    else:
        news_md = render(rows, errors)

    today = date.today()
    days_ahead = (2 - today.weekday()) % 7  # weekday(): Mon=0 .. Sun=6, Wed=2
    if days_ahead == 0:
        days_ahead = 7
    next_wednesday = today + timedelta(days=days_ahead)
    next_str = f"Wednesday, {next_wednesday.isoformat()} ~7:00 AM ET"

    if not update_report(news_md, today.isoformat(), next_str):
        return 1
    update_archive(news_md, today.isoformat())
    print(f"OK: refreshed report with {total} items across {len(rows)} sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
