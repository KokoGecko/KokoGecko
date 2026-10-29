"""Scanline contribution graph from real GitHub contribution data.

    python tools/scanline/contrib.py KokoGecko

With GITHUB_TOKEN set (as in the Action) it uses the GraphQL API. Without a token it reads
the public contributions calendar page, parsing attributes by name so a reordering of
GitHub's markup does not break it.

Each day is a 12 x 12 cell drawn as two horizontal rules; the activity level (0-4) sets the
rule thickness: the same brightness -> thickness idea as the hero.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

import sim
from export import write_svg
from font import text_rects, text_width
from theme import palettes
from timeline import Timeline

CELL, GAP, X0, Y0 = 12, 4, 48, 44
THICK = {1: 1, 2: 2, 3: 3, 4: 5}  # level -> rule thickness in px (two rules per cell)
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
QUERY = """query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  totalContributions weeks { contributionDays { date weekday contributionLevel } } } } } }"""


def _get(req):
    try:
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"contrib.py: {req.full_url} answered HTTP {e.code}")


def fetch_graphql(login, token):
    """[(week, weekday, date, level)] and the yearly total, from the GraphQL API."""
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={"Authorization": f"bearer {token}", "User-Agent": "scanline-contrib"})
    cal = json.loads(_get(req))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(w, d["weekday"], d["date"], LEVELS[d["contributionLevel"]])
            for w, week in enumerate(cal["weeks"]) for d in week["contributionDays"]]
    return days, cal["totalContributions"]


class _Calendar(HTMLParser):
    """Collects every calendar cell: <td data-date=... data-level=... id="contribution-day-component-ROW-COL">."""

    def __init__(self):
        super().__init__()
        self.days = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        m = re.fullmatch(r"contribution-day-component-(\d+)-(\d+)", a.get("id") or "")
        if tag == "td" and m and "data-date" in a and "data-level" in a:
            self.days.append((int(m.group(2)), int(m.group(1)), a["data-date"], int(a["data-level"])))


def fetch_html(login):
    """Same data from the public calendar page; no token needed."""
    req = urllib.request.Request(f"https://github.com/users/{login}/contributions",
                                 headers={"User-Agent": "scanline-contrib"})
    html = _get(req)
    cal = _Calendar()
    cal.feed(html)
    m = re.search(r"([\d,]+)\s+contributions?\s+in the last year", html)
    return cal.days, int(m.group(1).replace(",", "")) if m else None


def graph(days, total):
    weeks = max(d[0] for d in days) + 1
    w = X0 * 2 + weeks * (CELL + GAP) - GAP
    tl = Timeline(w, Y0 + 7 * (CELL + GAP) + 24, 1, sim.FPS, [], rest=0)
    tl.add(text_rects("contributions · last year", X0, 16, 2), "faint")
    if total is not None:
        tl.add(text_rects(f"{total}", w - X0 - text_width(f"{total}", 2), 16, 2))
    latest = max(d[2] for d in days)
    for week, weekday, date, level in days:
        x, y = X0 + week * (CELL + GAP), Y0 + weekday * (CELL + GAP)
        if level == 0:
            tl.add([(x + 4, y + 5, 4, 2)], "faint")           # an empty day is a faint sample tick
            continue
        t = THICK[level]
        tl.add([(x, y + 3 - t // 2, CELL, t), (x, y + 9 - t // 2, CELL, t)], "acc" if date == latest else "ink")
    return tl


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Draw the contribution calendar as scanlines.")
    ap.add_argument("login", help="GitHub username")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "..", "assets", "contrib"),
                    help="output folder (default assets/contrib)")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    days, total = fetch_graphql(args.login, token) if token else fetch_html(args.login)
    if not days:
        sys.exit("contrib.py: no contribution days found (has GitHub changed the page?)")
    os.makedirs(args.out, exist_ok=True)
    tl = graph(days, total)
    desc = f"{total} contributions in the last year, one scanline cell per day." if total else "Contribution graph."
    for mode, pal in palettes("b").items():
        size = write_svg(tl, pal, f"{args.out}/contrib-{mode}.svg", "Contribution graph", desc,
                         static=True, background=False)
        print(f"contrib-{mode}.svg {size / 1024:.1f} KB, {len(days)} days, total {total}")
