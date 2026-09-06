# Gem-finder

Finds fantasy football "gems" (sleepers/breakouts) using training camp, preseason, press-conference, beat-reporter, and second-half-of-2025 signals.

## 2026 report

- **[2026-fantasy-gems.md](2026-fantasy-gems.md)** — the full research digest and gem predictions for the 2026 season. Contains a fully-automated **"Auto-Refreshed News"** section that updates itself every Wednesday.

## Automatic weekly updates

A GitHub Actions workflow refreshes the report's news section **every Wednesday (~8 AM ET)** and stamps the refresh date.

| Piece | Where | What it does |
|---|---|---|
| Workflow | [`.github/workflows/update-gems.yml`](.github/workflows/update-gems.yml) | Cron schedule + manual trigger |
| Updater | [`.github/scripts/update_report.py`](.github/scripts/update_report.py) | Fetches RSS feeds, filters for NFL/fantasy news, rewrites the report |
| Feeds | in the script (`FEEDS` list) | RotoBaller, FantasyPros, ESPN NFL, ProFootballTalk (all public RSS) |
| Archive | `news-archive.md` (generated) | Keeps the last 14 weekly snapshots |
| Deps | [`requirements.txt`](requirements.txt) | `feedparser`, `requests` |

**How it works**

1. Every Wednesday the workflow checks out the repo, installs deps, and runs `update_report.py`.
2. The script pulls the latest headlines from the configured feeds, drops off-topic items (MLB/NBA/college, etc.), and prioritizes fantasy-relevant ones (sleeper, waiver, rankings, injury, depth chart, …).
3. It rewrites everything between `<!-- AUTO-NEWS-START -->` and `<!-- AUTO-NEWS-END -->` in the report, updates the "Last/Next auto-refresh" stamps, appends a dated snapshot to `news-archive.md`, and commits + pushes.

**Manual run:** Actions tab → **"Refresh Gems Report"** → **Run workflow**.

**Change the schedule:** edit the `cron` line in `.github/workflows/update-gems.yml` ([crontab syntax](https://crontab.guru)). Default: `0 12 * * 3` (Wednesdays, 12:00 UTC).

**Add/remove sources:** edit the `FEEDS` list at the top of `.github/scripts/update_report.py` — any standard RSS/Atom URL works.

> **⚠️ Default-branch note:** GitHub only fires `schedule` events from the repository's **default branch**. Until the workflow file is merged to `main`, the Wednesday schedule won't run automatically — use the manual "Run workflow" trigger (which works on any branch that has the file), or merge the PR that carries this automation.
