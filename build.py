#!/usr/bin/env python3
"""
build.py — regenerate /part-1/ … /part-5/ index pages from Airtable.

Reads Airtable credentials from env (AIRTABLE_API_KEY or AIRTABLE_TOKEN).
Fetches each of the 6 records individually (the long-form field is heavy).
Caches the raw long-form body and metadata to _cache/ for inspection.
Re-renders /part-N/index.html for N in 1..5 using a single template.
Does NOT regenerate /index.html — the landing page is hand-curated.

If no credentials are present, build.py falls back to whatever is already
in _cache/ so the site can be re-rendered offline once content has been
pulled at least once.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "_cache"
CACHE.mkdir(exist_ok=True)
IMG_DIR = ROOT / "assets" / "img"

BASE_ID = "appi63sF9wC7M0lbM"
TABLE_ID = "tbltPNwJpIszoBiCc"

PARTS = [
    {"part": 0, "record_id": "reclX6lcg0JYejlNV", "slug": "epstein-files-series-launch"},
    {"part": 1, "record_id": "recZg9XekID7WKKRE", "slug": "stop-doing-pedophile-math"},
    {"part": 2, "record_id": "recKpddZgNkam1LFu", "slug": "they-are-girls-treated-like-currency"},
    {"part": 3, "record_id": "recdAwIsINMWuh0EA", "slug": "more-true-and-more-false"},
    {"part": 4, "record_id": "reciRclOeQEFBOk5J", "slug": "they-knew-and-they-didnt-care"},
    {"part": 5, "record_id": "recK0b1gFZQMuTnPd", "slug": "you-dont-need-a-cabal"},
]

FIELDS = {
    "title":    "fldCuaUEpHPgM7cwP",
    "subtitle": "fldzp3GYuexCS9Viz",
    "body":     "fldsfZBkRCkpIML5o",
    "quotes":   "fldEr0oew5Y5A5DgV",
    "mj":       "fldNuHIx9TOXcxtsA",
    "anchor":   "fldpnkxjKcMZtM91g",
    "date":     "fldZYnkYWb6eyYGCm",
    "slug":     "fldCp1fpb9wV6PGWK",
    "seo":      "fldDeu3t5AWKUTwZj",
}

USE_WHEN = {
    1: "someone tries to minimize what was done to Epstein’s victims by pointing out their ages, their appearance, their apparent maturity, or the clinical distinction between pedophilia and ephebophilia.",
    2: "the conversation is moving too fast toward accountability for powerful men and not fast enough toward the girls who are still alive, who are still carrying this, and who were re-victimized by the release itself.",
    3: "someone conflates the documented record with the conspiracy theories, or when someone dismisses the entire case because of the conspiracy theories, or when you are trying to hold the truth steady against both distortions.",
    4: "someone asks what the files actually show about the people currently in power, or when the conversation needs grounding in documented facts rather than allegation.",
    5: "you need the full argument — when someone wants to understand not just what happened but what it means, and what accountability actually requires.",
}

SHORT_TITLES = {
    1: "Stop Doing <em>Pedophile Math</em>",
    2: "They Are <em>Girls</em>. And They Were Treated Like <em>Currency</em>.",
    3: "<em>More True</em> and <em>More False</em>",
    4: "They <em>Knew</em>. And They <em>Didn’t Care</em>.",
    5: "You Don’t Need a <em>Cabal</em>. You Just Need a World That <em>Doesn’t Care</em>.",
}

PROD_BASE = "https://moretruemorefalse.laboracollective.com"


# ─────────────────────────── Airtable fetch ───────────────────────────

def airtable_token() -> Optional[str]:
    return os.environ.get("AIRTABLE_API_KEY") or os.environ.get("AIRTABLE_TOKEN")


def fetch_record(record_id: str, token: str) -> dict:
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}/{record_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_part_data(part: dict, token: Optional[str], log: list[str]) -> dict:
    """Return {title, subtitle, body, date, slug, seo} for one part."""
    rid = part["record_id"]
    cache_json = CACHE / f"part{part['part']}.json"
    cache_body = CACHE / f"part{part['part']}.txt"

    if token:
        try:
            rec = fetch_record(rid, token)
            f = rec.get("fields", {})
            data = {
                "part":     part["part"],
                "record":   rid,
                "title":    f.get("Article Title") or f.get("Title") or "",
                "subtitle": f.get("Subtitle") or "",
                "body":     f.get("Output – Final Long Form") or f.get("Output - Final Long Form") or "",
                "date":     f.get("Scheduled Date") or "",
                "slug":     f.get("Slug") or part["slug"],
                "seo":      f.get("Alt Title + SEO") or "",
            }
            cache_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            cache_body.write_text(data["body"] or "", encoding="utf-8")
            log.append(f"  ↳ fetched Part {part['part']} from Airtable")
            return data
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            log.append(f"  ⚠ Airtable fetch failed for Part {part['part']}: {e}. Falling back to cache.")

    if cache_json.exists():
        data = json.loads(cache_json.read_text(encoding="utf-8"))
        log.append(f"  ↳ loaded Part {part['part']} from cache")
        return data

    raise SystemExit(
        f"No Airtable token and no cache for Part {part['part']} "
        f"(_cache/part{part['part']}.json missing). Set AIRTABLE_API_KEY and re-run."
    )


# ─────────────────────────── body rendering ───────────────────────────

# Lines that look like a section heading (Title Case, no terminal punctuation,
# short, doesn't start with quote). Used to wrap them in <h3>.
HEADING_TERMS = "?.!\":"

# Patterns that should never be treated as a heading even if they look short:
NON_HEADING_PREFIXES = ("—", "•", "“", "\"", "*", "→")


def is_divider(line: str) -> bool:
    s = line.strip()
    return s == "⸻" or s == "---"


def is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 90:
        return False
    if s[0] in NON_HEADING_PREFIXES:
        return False
    if s[-1] in HEADING_TERMS:
        if s[-1] != "?":
            return False
    words = re.findall(r"[A-Za-z][A-Za-z'’-]+", s)
    if len(words) < 3:
        return False
    caps = sum(1 for w in words if w[0].isupper())
    if caps / max(len(words), 1) < 0.5:
        return False
    if re.search(r"[.!?]\s+[A-Z]", s):
        return False
    return True


def is_attribution(line: str) -> bool:
    s = line.strip()
    return s.startswith("—") or s.startswith("--")


def inline_markdown(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", text)
    return text


def render_body(raw: str, part_num: int) -> str:
    """Render the essay body to HTML. Drops the opening title/byline lines
    that already appear in the anchor banner and meta strip."""
    raw = raw.replace("\r\n", "\n").strip()
    lines = raw.split("\n")

    # Skip leading byline / title block. The Airtable body starts with:
    #   PART X / Title / By Dr. Yamicia Connor ... / blank / epigraph quote / — attribution
    # We drop the duplicate "PART X" + title + byline because they already
    # appear in the anchor banner. The epigraph + attribution stay.
    stripped: list[str] = []
    seen_byline = False
    for line in lines:
        s = line.strip()
        if not seen_byline:
            if not s:
                continue
            if s.upper().startswith("PART "):
                continue
            if s.lower().startswith("by dr.") or s.lower().startswith("by yamicia"):
                seen_byline = True
                continue
            # Anything before the byline (typically the duplicate title line)
            # is part of the article header — skip it.
            continue
        else:
            stripped.append(line)

    # Group into blocks separated by blank lines.
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in stripped:
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)

    out: list[str] = []
    seen_epigraph = False
    for block in blocks:
        joined = " ".join(l.strip() for l in block).strip()
        first = block[0].strip()

        # divider
        if len(block) == 1 and is_divider(first):
            out.append('<div class="divider" role="separator" aria-hidden="true"></div>')
            continue

        # epigraph quote (curly-quote wrapped opening line near top)
        if not seen_epigraph and len(block) == 1 and (first.startswith("“") and first.endswith("”")):
            out.append(f'<blockquote class="epigraph">{inline_markdown(first)}</blockquote>')
            seen_epigraph = True
            continue

        # attribution caption after an epigraph
        if len(block) == 1 and is_attribution(first):
            out.append(f'<p class="attribution">{inline_markdown(first)}</p>')
            continue

        # heading (single short title-case line)
        if len(block) == 1 and is_heading(first):
            out.append(f"<h3>{inline_markdown(first)}</h3>")
            continue

        # signoff: lines that look like "— Dr. Yamicia Connor..."
        if len(block) == 1 and first.startswith("—") and "Connor" in first:
            out.append(f'<p class="signoff">{inline_markdown(first)}</p>')
            continue

        # plain paragraph — collapse internal newlines into spaces
        out.append(f"<p>{inline_markdown(joined)}</p>")

    return "\n".join(out)


# ─────────────────────────── HTML templates ───────────────────────────

LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_tag}</title>
<meta name="description" content="{description}">
<meta name="author" content="Dr. Yamicia Connor, MD, PhD, MPH">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta property="og:site_name" content="The Labora Collective">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{og_image}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,400;1,500&family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Jost:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/series.css">
</head>
<body class="{body_class}">
{nav}
{content}
{footer}
</body>
</html>
"""

NAV = """<nav class="site-nav" aria-label="Site">
  <div class="inner">
    <a class="brand" href="/"><span class="mark">More True &amp; More False</span></a>
    <a class="crumb" href="/"><span class="sep">←</span> The Series</a>
  </div>
</nav>
"""

FOOTER = """<footer class="site-footer">
  <div class="inner">
    <div class="colophon">More True and <em>More False</em> — a series by Dr. Yamicia Connor.</div>
    <div>Published by <a href="https://laboracollective.com">The Labora Collective</a> · In Her Name · 2026</div>
  </div>
</footer>
"""

ESSAY_TPL = """<header class="anchor {anchor_class}">{anchor_img}<div class="overlay"></div>
  <div class="anchor-inner">
    <div class="eyebrow">Part {part_word} · The Epstein Files Series</div>
    <h1>{display_title}</h1>
    <p class="dek">{subtitle}</p>
  </div>
</header>
<section class="meta-strip">
  <div class="inner">
    <span class="author">Dr. Yamicia Connor, MD, PhD, MPH</span>
    <span class="sep">·</span>
    <span class="journal">In Her Name · Labora Signal</span>
    <span class="sep">·</span>
    <span class="date">{pretty_date}</span>
  </div>
</section>
<main>
  <article class="prose">
    <div class="use-when">
      <strong>Use this when</strong>
      Use this when {use_when}
    </div>
{body_html}
  </article>
</main>
<nav class="piece-nav" aria-label="Series navigation">
  <div class="inner">
    <a class="prev" href="{prev_href}">
      <span class="label">{prev_label}</span>
      <span class="title">{prev_title}</span>
    </a>
    <a class="next" href="{next_href}">
      <span class="label">{next_label}</span>
      <span class="title">{next_title}</span>
    </a>
  </div>
</nav>
"""


PART_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}

NAV_DATA = {
    1: {
        "prev": ("/", "← The Series", "More True and More False"),
        "next": ("/part-2/", "Next — Part Two", "They Are Girls. And They Were Treated Like Currency."),
    },
    2: {
        "prev": ("/part-1/", "← Part One", "Stop Doing Pedophile Math"),
        "next": ("/part-3/", "Next — Part Three", "More True and More False"),
    },
    3: {
        "prev": ("/part-2/", "← Part Two", "They Are Girls. And They Were Treated Like Currency."),
        "next": ("/part-4/", "Next — Part Four", "They Knew. And They Didn’t Care."),
    },
    4: {
        "prev": ("/part-3/", "← Part Three", "More True and More False"),
        "next": ("/part-5/", "Next — Part Five", "You Don’t Need a Cabal."),
    },
    5: {
        "prev": ("/part-4/", "← Part Four", "They Knew. And They Didn’t Care."),
        "next": ("/", "Back to → The Series", "More True and More False"),
    },
}


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def pretty_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d").date()
        return d.strftime("%B %d, %Y").replace(" 0", " ")
    except ValueError:
        return iso


def render_essay(data: dict, log: list[str]) -> str:
    part_num = data["part"]
    slug = data.get("slug") or PARTS[part_num]["slug"]
    title = data.get("title") or ""
    subtitle = data.get("subtitle") or ""
    body_raw = data.get("body") or ""
    date_iso = data.get("date") or ""

    if not body_raw:
        log.append(f"  ⚠ Part {part_num}: Output – Final Long Form is empty.")
    if not subtitle:
        log.append(f"  ⚠ Part {part_num}: Subtitle is empty.")

    body_html = render_body(body_raw, part_num)

    # Anchor banner (image or no-image)
    hero_path = IMG_DIR / f"part-{part_num}-hero.jpg"
    if hero_path.exists():
        anchor_class = ""
        alt = html_escape(f"{title} — anchor image")
        anchor_img = f'<img src="/assets/img/part-{part_num}-hero.jpg" alt="{alt}">'
        og_image = f"{PROD_BASE}/assets/img/part-{part_num}-hero.jpg"
    else:
        anchor_class = "no-image"
        anchor_img = ""
        og_image = f"{PROD_BASE}/assets/img/og-card.jpg"

    display_title = SHORT_TITLES.get(part_num, html_escape(title))

    nav = NAV_DATA[part_num]
    use_when_text = USE_WHEN[part_num]

    title_plain = title.replace("Part %d:" % part_num, "").strip().lstrip(":").strip()
    title_tag = f"{title_plain} — More True and More False — The Labora Collective"
    canonical = f"{PROD_BASE}/part-{part_num}/"

    essay_html = ESSAY_TPL.format(
        anchor_class=anchor_class,
        anchor_img=anchor_img,
        part_word=PART_WORDS[part_num],
        display_title=display_title,
        subtitle=html_escape(subtitle),
        pretty_date=pretty_date(date_iso),
        use_when=use_when_text,
        body_html=body_html,
        prev_href=nav["prev"][0],
        prev_label=nav["prev"][1],
        prev_title=nav["prev"][2],
        next_href=nav["next"][0],
        next_label=nav["next"][1],
        next_title=nav["next"][2],
    )

    return LAYOUT.format(
        title_tag=html_escape(title_tag),
        description=html_escape(subtitle),
        og_title=html_escape(f"Part {PART_WORDS[part_num]}: {title_plain}"),
        canonical=canonical,
        og_image=og_image,
        body_class="cadence-essay",
        nav=NAV,
        content=essay_html,
        footer=FOOTER,
    )


# ─────────────────────────── main ───────────────────────────

def main() -> int:
    log: list[str] = []
    token = airtable_token()
    if not token:
        log.append("⚠ No AIRTABLE_API_KEY / AIRTABLE_TOKEN in env — using _cache/ only.")
    else:
        log.append("✓ Airtable token detected.")

    log.append("")
    log.append("Loading parts:")

    # Part 0 is hand-curated; we still cache it for inspection.
    for part in PARTS:
        load_part_data(part, token, log)

    log.append("")
    log.append("Rendering essay pages:")
    written: list[Path] = []
    for part in PARTS[1:]:
        data = json.loads((CACHE / f"part{part['part']}.json").read_text(encoding="utf-8"))
        html = render_essay(data, log)
        out = ROOT / f"part-{part['part']}" / "index.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(html, encoding="utf-8")
        written.append(out)
        log.append(f"  ✓ wrote {out.relative_to(ROOT)} ({len(html):,} bytes)")

    log.append("")
    images_present = sum(1 for p in range(1, 6) if (IMG_DIR / f"part-{p}-hero.jpg").exists())
    log.append(f"Anchor images: {images_present} of 5 present in /assets/img/")
    log.append("Landing page /index.html is hand-curated — not regenerated.")
    log.append("")
    log.append(f"Wrote {len(written)} essay page(s). Done.")

    print("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
