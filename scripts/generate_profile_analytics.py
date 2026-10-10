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
source_levels = {}
for item in payload["contributions"]:
    try:
        d = datetime.strptime(item["date"], "%Y-%m-%d").date()
        n = int(item.get("count", 0))
    except (KeyError, TypeError, ValueError):
        continue
    contribs.append((d, max(0, n)))
    # The source returns GitHub's real 0–4 activity level for each calendar day.
    # Preserve it instead of re-binning every positive day into the same shade.
    try:
        source_level = int(item.get("level", -1))
    except (TypeError, ValueError):
        source_level = -1
    if 0 <= source_level <= 4:
        source_levels[d] = source_level

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

today = datetime.now(timezone.utc).date()

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

# Keep a rolling 26-week window anchored to the current calendar week, not the
# latest date returned by the upstream scraper. This prevents October/current-week
# activity from disappearing when a cached/source response ends a day early.
grid_end = today + timedelta(days=(6 - today.weekday()))  # Sunday of the current week.
grid_start = grid_end - timedelta(days=181)  # Monday, 25 weeks before grid_end.
recent_days = []
for i in range(182):
    d = grid_start + timedelta(days=i)
    recent_days.append((d, counts.get(d, 0)))
source_last_date = max((d for d, _ in contribs if d <= today), default=grid_start)
source_lag_days = max(0, (today - source_last_date).days)
today_count = counts.get(today, 0)
yesterday_count = counts.get(today - timedelta(days=1), 0)

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
    W, H = 1200, 280
    panel = "#0B1220"
    muted = "#8FA3BD"
    text_color = "#E2E8F0"
    blue = "#3B82F6"
    levels = ["#172033", "#1E3A5F", "#1D4ED8", "#3B82F6", "#7DD3FC"]

    total = sum(value for _, value in recent_days)
    active_days = sum(1 for _, value in recent_days if value > 0)
    positive_counts = sorted(value for _, value in contribs if value > 0)

    # Prefer the upstream GitHub 0–4 intensity class. Only fall back to a
    # percentile rank if the source omits a day's level.
    from bisect import bisect_right

    def level_for(day: date, value: int) -> int:
        source_level = source_levels.get(day)
        if source_level is not None:
            return source_level
        if value <= 0:
            return 0
        if not positive_counts:
            return 1
        percentile = bisect_right(positive_counts, value) / len(positive_counts)
        return max(1, min(4, int(math.ceil(percentile * 4))))

    gx, gy, cell, gap = 285, 91, 18, 6
    cell_step = cell + gap
    cells = []
    month_labels = []
    previous_month = None

    for i, (d, value) in enumerate(recent_days):
        col = i // 7
        row = d.weekday()  # Monday to Sunday.
        x = gx + col * cell_step
        y = gy + row * cell_step
        level = level_for(d, value)
        cells.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" '
            f'fill="{levels[level]}" stroke="#93C5FD" stroke-opacity=".10">'
            f'<title>{d.isoformat()}: {value} contributions</title></rect>'
        )
        month_key = (d.year, d.month)
        if month_key != previous_month:
            month_labels.append(
                f'<text x="{x}" y="76" font-size="11" font-weight="700" fill="{muted}">{d.strftime("%b")}</text>'
            )
            previous_month = month_key

    weekdays = []
    for label, row in (("M", 0), ("W", 2), ("F", 4)):
        y = gy + row * cell_step + 13
        weekdays.append(
            f'<text x="265" y="{y}" text-anchor="end" font-size="10" fill="{muted}">{label}</text>'
        )

    legend = []
    legend_labels = ["Less", "", "", "", "More"]
    lx, ly = 958, 142
    for level, color in enumerate(levels):
        x = lx + level * 30
        legend.append(
            f'<rect x="{x}" y="{ly}" width="20" height="20" rx="4" fill="{color}"/>'
        )
    legend_svg = "".join(legend)
    legend_label = (
        f'<text x="{lx}" y="{ly-13}" font-size="11" font-weight="700" fill="{text_color}">DAILY INTENSITY</text>'
        f'<text x="{lx}" y="{ly+41}" font-size="10" fill="{muted}">Less</text>'
        f'<text x="{lx+140}" y="{ly+41}" text-anchor="end" font-size="10" fill="{muted}">More</text>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {W} {H}" role="img" aria-label="{USERNAME} contribution heatmap for 26 weeks, source through {source_last_date.isoformat()}">
<defs>
  <linearGradient id="accent" x1="0" x2="1">
    <stop offset="0" stop-color="#2563EB"/><stop offset="1" stop-color="#38BDF8"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{H}" rx="16" fill="{panel}"/>
<rect x="0" y="0" width="5" height="{H}" rx="2.5" fill="url(#accent)"/>
<text x="30" y="39" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="13" font-weight="800" letter-spacing="1.8" fill="#93C5FD">CONTRIBUTION RHYTHM</text>
<text x="30" y="61" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="11" fill="{muted}">26 weeks · {active_days} active days</text>
<text x="30" y="127" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="35" font-weight="800" fill="{text_color}">{total}</text>
<text x="30" y="147" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="10" font-weight="700" letter-spacing="1" fill="{muted}">CONTRIBUTIONS</text>
<line x1="30" y1="165" x2="228" y2="165" stroke="#2A3C56"/>
<text x="30" y="187" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="9" font-weight="700" letter-spacing=".7" fill="{muted}">TODAY · {today.strftime("%d %b").upper()}</text>
<text x="30" y="211" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="24" font-weight="800" fill="{blue}">{today_count}</text>
<text x="130" y="187" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="9" font-weight="700" letter-spacing=".3" fill="{muted}">YESTERDAY · {(today - timedelta(days=1)).strftime("%d %b").upper()}</text>
<text x="130" y="211" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="24" font-weight="800" fill="#7DD3FC">{yesterday_count}</text>
<text x="30" y="239" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="9" fill="{muted}">Source through {source_last_date.strftime("%d %b").upper()}</text>
<g font-family="Segoe UI, Ubuntu, Arial, sans-serif">
  {"".join(weekdays)}
  {"".join(month_labels)}
  {"".join(cells)}
  {legend_svg}
  {legend_label}
</g>
</svg>"""
streak = streak_svg()
activity = activity_svg()

# Version 5 uses the professional blue palette.
Path("dist/github-streak-v5.svg").write_text(streak, encoding="utf-8")
Path("dist/github-activity-v5.svg").write_text(activity, encoding="utf-8")

# Keep the original Version 2 pink analytics available for rollback.
streak_pink_v2 = streak.replace("#3B82F6", "#FF69B4").replace("#CBD5E1", "#F8BBD0")
activity_pink_v2 = (
    activity.replace("#3B82F6", "#FF69B4")
    .replace("#CBD5E1", "#F8BBD0")
    .replace("#60A5FA", "#EF93C4")
    .replace("#0B1220", "#181C24")
    .replace("#1D4ED8", "#FF1493")
)
Path("dist/github-streak-pink-v2.svg").write_text(streak_pink_v2, encoding="utf-8")
Path("dist/github-activity-pink-v2.svg").write_text(activity_pink_v2, encoding="utf-8")


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
    "activity_active_days": sum(1 for _, value in recent_days if value > 0),
    "source_data_through": source_last_date.isoformat(),
    "source_lag_days": source_lag_days,
    "today_count": today_count,
    "yesterday_count": yesterday_count,
}, indent=2))
