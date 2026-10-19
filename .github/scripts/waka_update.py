#!/usr/bin/env python3
"""
WakaTime -> README generator.

Replaces everything between <!--START_SECTION:waka--> and <!--END_SECTION:waka-->
in README.md with fresh WakaTime stats.

Why not the stock anmol098/waka-readme-stats action:

  * its "Code Time" badge is taken from stats/all_time, while the language table
    comes from stats/last_7_days -> the two numbers never add up (86h vs 28h),
  * every table is hard-cut to the top 5 rows (make_list(top_num=5)), so
    Lua / JavaScript / Rust / HTML / PowerShell / YAML are silently dropped,
  * the range of each number is not written anywhere, so it looks broken.

This script keeps the same visual style, but every table is complete and the
time range of every number is written next to it.

Env:
  WAKATIME_API_KEY   (required)
  WAKATIME_API_URL   (optional, default https://wakatime.com/api/v1/)
  README_PATH        (optional, default README.md)
  SECTION_NAME       (optional, default waka)
  TOP_N              (optional, default 20 - max rows per table)
  MIN_PERCENT        (optional, default 0.1 - hide dust entries)
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("WAKATIME_API_URL", "https://wakatime.com/api/v1/").rstrip("/") + "/"
KEY = os.environ.get("WAKATIME_API_KEY", "")
README_PATH = os.environ.get("README_PATH", "README.md")
SECTION = os.environ.get("SECTION_NAME", "waka")
TOP_N = int(os.environ.get("TOP_N", "20"))
MIN_PERCENT = float(os.environ.get("MIN_PERCENT", "0.1"))

BAR_WIDTH = 25


def fetch(path):
    """GET a WakaTime API endpoint and return the parsed JSON."""
    url = f"{API}{path}?api_key={KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": "waka-readme-stats"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def human(seconds):
    """Format seconds the way WakaTime does it."""
    seconds = int(round(seconds))
    hours, minutes = divmod(seconds, 3600)
    minutes //= 60
    if hours:
        return f"{hours} hrs {minutes} mins"
    if minutes:
        return f"{minutes} mins"
    return f"{seconds} secs"


def bar(percent):
    """Text progress bar, 25 characters wide."""
    filled = max(0, min(BAR_WIDTH, round(percent / 100 * BAR_WIDTH)))
    return "\u2588" * filled + "\u2591" * (BAR_WIDTH - filled)


def rows_from(items, limit=TOP_N):
    """Turn a WakaTime stats list into (name, text, percent) rows, sorted by time."""
    rows = []
    for item in items or []:
        name = item.get("name", "?")
        text = item.get("text") or human(item.get("total_seconds", 0))
        percent = float(item.get("percent", 0))
        seconds = item.get("total_seconds", 0) or 0
        if seconds <= 0 or percent < MIN_PERCENT:
            continue
        rows.append((name, text, percent, seconds))
    rows.sort(key=lambda row: row[3], reverse=True)
    return rows[:limit]


def table(rows):
    """Render rows as a fixed width text table."""
    if not rows:
        return "no activity tracked yet"
    out = []
    for name, text, percent, _ in rows:
        short = name[:25]
        out.append(f"{short}{' ' * (25 - len(short))}{text:<20}{bar(percent)}   {percent:05.2f} % ")
    return "\n".join(out)


def badge(label, value, color):
    """shields.io badge with an url encoded label/value."""
    from urllib.parse import quote

    return (
        f"![{label}](https://img.shields.io/badge/{quote(label)}-{quote(value)}-{color}"
        f"?style=flat-square)"
    )


def build(all_time, week):
    """Build the whole markdown block that goes between the section markers."""
    a = all_time.get("data", {})
    w = week.get("data", {})

    all_langs = rows_from(a.get("languages"))
    week_langs = rows_from(w.get("languages"))
    week_editors = rows_from(w.get("editors"))
    week_os = rows_from(w.get("operating_systems"))
    week_projects = rows_from(w.get("projects"))

    total_all = a.get("human_readable_total") or human(a.get("total_seconds", 0))
    total_week = w.get("human_readable_total") or human(w.get("total_seconds", 0))

    top_lang = all_langs[0][0] if all_langs else "?"

    parts = [
        badge("Code Time", total_all, "blue"),
        badge("This Week", total_week, "green"),
        badge("Top Language", top_lang, "orange"),
        "",
        f"**Total code time: {total_all}** (all time, since {a.get('start', '?')[:10]})",
        "",
        "\U0001F4CA **All time - Programming Languages**",
        "",
        "```text",
        table(all_langs),
        "```",
        "",
        f"\U0001F4CA **This week - {total_week}** (last 7 days)",
        "",
        "```text",
        table(week_langs),
        "```",
        "",
    ]

    extras = []
    if week_projects:
        extras += ["**Projects this week**", "", "```text", table(week_projects), "```", ""]
    if week_editors:
        extras += ["**Editors this week**", "", "```text", table(week_editors), "```", ""]
    if week_os:
        extras += ["**OS this week**", "", "```text", table(week_os), "```", ""]
    if extras:
        parts += ["<details>", "<summary>More details for this week</summary>", ""] + extras + ["</details>", ""]

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M:%S")
    parts += ["", f" Last Updated on {stamp} UTC"]
    return "\n".join(parts)


def replace_section(readme, content):
    """Swap the content between the START/END markers, keeping the markers."""
    start = f"<!--START_SECTION:{SECTION}-->"
    end = f"<!--END_SECTION:{SECTION}-->"
    if start not in readme or end not in readme:
        raise SystemExit(f"markers {start} / {end} not found in {README_PATH}")
    head, rest = readme.split(start, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{start}\n{content}\n{end}{tail}"


def main():
    if not KEY:
        raise SystemExit("WAKATIME_API_KEY is not set")

    all_time = fetch("users/current/stats/all_time")
    week = fetch("users/current/stats/last_7_days")

    with open(README_PATH, "r", encoding="utf-8", newline="") as fh:
        readme = fh.read()

    crlf = "\r\n" in readme
    content = build(all_time, week)
    if crlf:
        content = content.replace("\n", "\r\n")

    new_readme = replace_section(readme, content)

    if new_readme == readme:
        print("README already up to date")
        return

    with open(README_PATH, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_readme)
    print("README updated")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        raise SystemExit(f"wakatime request failed: {exc}")
