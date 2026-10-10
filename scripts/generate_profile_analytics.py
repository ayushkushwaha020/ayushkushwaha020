#!/usr/bin/env python3
import json
import math
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

USERNAME = "ayushkushwaha020"
API_URL = f"https://github-contributions-api.jogruber.de/v4/{USERNAME}?y=last"
OUT = Path("dist")
OUT.mkdir(parents=True, exist_ok=True)

req = urllib.request.Request(
    API_URL,
    headers={
        "User-Agent": "ayushkushwaha020-github-profile-analytics",
        "Cache-Control": "no-cache",
    },
)
with urllib.request.urlopen(req, timeout=30) as response:
    payload = json.load(response)

if "contributions" not in payload:
    raise RuntimeError(f"Contribution API response missing contributions: {payload}")

contribs = []
for item in payload["contributions"]:
    try:
        d = datetime.strptime(item["date"], "%Y-%m-%d").date()
        n = int(item.get("count", 0))
    except (KeyError, TypeError, ValueError):
        continue
    contribs.append((d, max(0, n)))

contribs.sort(key=lambda x: x[0])
if not contribs:
    raise RuntimeError("No contribution data returned")

counts = {d: n for d, n in contribs}
last_year_total = None
totals = payload.get("total", {})
if isinstance(totals, dict):
    if "lastYear" in totals:
        last_year_total = int(totals["lastYear"])
    elif totals:
        last_year_total = sum(int(v) for v in totals.values())
if last_year_total is None:
    last_year_total = sum(n for _, n in contribs)

today = date.today()

# GitHub-style current streak: today may be zero without breaking a streak.
cursor = today
if counts.get(today, 0) == 0:
    cursor = today - timedelta(days=1)

current = 0
while counts.get(cursor, 0) > 0:
    current += 1
    cursor -= timedelta(days=1)

longest = 0
run = 0
prev = None
for d, n in contribs:
    if n > 0:
        if prev is not None and d == prev + timedelta(days=1):
            run += 1
        else:
            run = 1
        longest = max(longest, run)
        prev = d
    else:
        run = 0
        prev = None

recent_days = []
end = max(d for d, _ in contribs)
start = end - timedelta(days=89)
for i in range(90):
    d = start + timedelta(days=i)
    recent_days.append((d, counts.get(d, 0)))

def esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

def streak_svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 900 240" role="img" aria-label="{USERNAME} GitHub contribution streak statistics">
<defs>
  <filter id="glow" x="-20%" y="-30%" width="140%" height="160%">
    <feGaussianBlur stdDeviation="4" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<rect width="900" height="240" rx="10" fill="transparent"/>
<g font-family="Segoe UI, Ubuntu, Arial, sans-serif" text-anchor="middle">
  <g>
    <text x="150" y="92" font-size="44" font-weight="800" fill="#3B82F6" filter="url(#glow)">{last_year_total}</text>
    <text x="150" y="132" font-size="18" font-weight="700" fill="#3B82F6">Total Contributions</text>
    <text x="150" y="158" font-size="13" fill="#CBD5E1">Last 12 Months</text>
  </g>
  <g>
    <text x="450" y="92" font-size="44" font-weight="800" fill="#3B82F6" filter="url(#glow)">{current}</text>
    <text x="450" y="132" font-size="18" font-weight="700" fill="#3B82F6">Current Streak</text>
    <text x="450" y="158" font-size="13" fill="#CBD5E1">{esc(USERNAME)}</text>
  </g>
  <g>
    <text x="750" y="92" font-size="44" font-weight="800" fill="#3B82F6" filter="url(#glow)">{longest}</text>
    <text x="750" y="132" font-size="18" font-weight="700" fill="#3B82F6">Longest Streak</text>
    <text x="750" y="158" font-size="13" fill="#CBD5E1">Recorded streak</text>
  </g>
</g>
<g stroke="#3B82F6" stroke-opacity=".18">
  <line x1="300" y1="45" x2="300" y2="185"/>
  <line x1="600" y1="45" x2="600" y2="185"/>
</g>
</svg>"""

def activity_svg() -> str:
    W, H = 1200, 380
    left, right, top, bottom = 70, 30, 35, 65
    plot_w, plot_h = W - left - right, H - top - bottom
    max_value = max(v for _, v in recent_days)
    if max_value == 0:
        max_value = 1

    points = []
    for i, (_, value) in enumerate(recent_days):
        x = left + (plot_w * i / (len(recent_days) - 1))
        y = top + plot_h * (1 - value / max_value)
        points.append((x, y, value))

    line = " ".join(
        ("M" if i == 0 else "L") + f" {x:.1f},{y:.1f}"
        for i, (x, y, _) in enumerate(points)
    )
    area = (
        f"M {points[0][0]:.1f},{top + plot_h:.1f} "
        + " ".join(f"L {x:.1f},{y:.1f}" for x, y, _ in points)
        + f" L {points[-1][0]:.1f},{top + plot_h:.1f} Z"
    )

    grid = []
    for step in range(5):
        frac = step / 4
        y = top + plot_h * frac
        value = round(max_value * (1 - frac))
        grid.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{W-right}" y2="{y:.1f}" '
            f'stroke="#3B82F6" stroke-opacity=".14"/>'
            f'<text x="{left-12}" y="{y+5:.1f}" text-anchor="end" font-size="12" fill="#CBD5E1">{value}</text>'
        )

    labels = []
    seen_months = set()
    for i, (d, _) in enumerate(recent_days):
        month_key = (d.year, d.month)
        if month_key in seen_months:
            continue
        seen_months.add(month_key)
        x = left + (plot_w * i / (len(recent_days) - 1))
        labels.append(
            f'<text x="{x:.1f}" y="{H-25}" text-anchor="middle" font-size="12" font-weight="700" fill="#CBD5E1">{d.strftime("%b")}</text>'
        )

    circles = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#CBD5E1"><title>{d.isoformat()}: {v} contributions</title></circle>'
        for (d, v), (x, y, _) in zip(recent_days, points)
        if v > 0
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {W} {H}" role="img" aria-label="{USERNAME} GitHub contribution activity graph">
<defs>
  <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
    <stop offset="0" stop-color="#60A5FA" stop-opacity=".28"/>
    <stop offset="1" stop-color="#60A5FA" stop-opacity=".02"/>
  </linearGradient>
  <filter id="glow" x="-10%" y="-20%" width="120%" height="140%">
    <feGaussianBlur stdDeviation="3" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<rect width="{W}" height="{H}" rx="10" fill="#0B1220"/>
<g font-family="Segoe UI, Ubuntu, Arial, sans-serif">
  {''.join(grid)}
  <path d="{area}" fill="url(#area)"/>
  <path d="{line}" fill="none" stroke="#3B82F6" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
  {circles}
  {''.join(labels)}
</g>
</svg>"""

(Path("dist/github-streak-v5.svg")).write_text(streak_svg(), encoding="utf-8")
(Path("dist/github-activity-v5.svg")).write_text(activity_svg(), encoding="utf-8")


# A small daily engineering reminder. The selected quote changes once per UTC day.
DEVELOPER_QUOTES = [
    "Build systems that make the right thing easier.",
    "Small, tested changes compound into reliable software.",
    "Make it work, make it clear, then make it better.",
    "Good code serves the next person who reads it.",
    "Automate repetition; spend judgment where it matters.",
    "Debug with evidence, not assumptions.",
    "Ship useful improvements, not just activity.",
    "Readable code is a gift to your future self.",
    "Every bug is a chance to improve the feedback loop.",
    "Measure twice, refactor once.",
    "Strong software is built through steady iteration.",
    "Learn the fundamentals; tools will keep changing.",
    "Simple interfaces hide difficult engineering well.",
    "Write tests for the behavior you want to preserve.",
    "Consistency beats occasional bursts of intensity.",
    "The best feature is one that solves a real problem.",
    "Prefer clear trade-offs over clever surprises.",
    "Good engineering makes change safer.",
]
daily_quote = DEVELOPER_QUOTES[today.toordinal() % len(DEVELOPER_QUOTES)]
quote_date = today.strftime("%d %b %Y").upper()
quote_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 1200 190" role="img" aria-label="Daily developer quote for {quote_date}">
<defs>
  <linearGradient id="accent" x1="0" x2="1">
    <stop offset="0" stop-color="#2563EB"/>
    <stop offset="1" stop-color="#38BDF8"/>
  </linearGradient>
</defs>
<rect width="1200" height="190" rx="12" fill="#0B1220"/>
<rect x="30" y="26" width="5" height="138" rx="2.5" fill="url(#accent)"/>
<text x="58" y="58" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="13" font-weight="700" letter-spacing="2.2" fill="#93C5FD">DAILY DEVELOPER QUOTE</text>
<text x="58" y="105" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="25" font-weight="600" fill="#F8FAFC">{esc(daily_quote)}</text>
<text x="58" y="144" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="13" letter-spacing="1.2" fill="#94A3B8">{quote_date}  ·  A DAILY ENGINEERING REMINDER</text>
<path d="M1050 0V44H1100V82H1200" fill="none" stroke="#60A5FA" stroke-width="1.5" stroke-opacity=".35"/>
<circle cx="1100" cy="44" r="4" fill="#38BDF8" opacity=".8"/>
</svg>"""
Path("dist/developer-quote-v5.svg").write_text(quote_svg, encoding="utf-8")

print(json.dumps({
    "username": USERNAME,
    "last_year_total": last_year_total,
    "current_streak": current,
    "longest_streak": longest,
    "activity_days": len(recent_days),
    "activity_total": sum(v for _, v in recent_days),
}, indent=2))
