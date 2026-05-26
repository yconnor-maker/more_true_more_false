# lc-more-true-and-more-false

Campaign site for **More True and More False** — a six-piece series by
Dr. Yamicia Connor on the Epstein files, published under The Labora Collective.

Production URL: `https://moretruemorefalse.laboracollective.com/`

## What this is

A static HTML + CSS site. No build framework, no JS dependencies. The
landing page (`/index.html`) is hand-curated. The five essay pages
(`/part-1/` through `/part-5/`) are templated and regenerated from
Airtable by `build.py`.

## Layout

```
.
├── index.html                # Hand-curated landing (Part 0 content)
├── part-1/index.html         # Stop Doing Pedophile Math
├── part-2/index.html         # They Are Girls. And They Were Treated Like Currency.
├── part-3/index.html         # More True and More False
├── part-4/index.html         # They Knew. And They Didn’t Care.
├── part-5/index.html         # You Don’t Need a Cabal.
├── part-0/index.html         # Redirect to /
├── 404.html
├── assets/
│   ├── css/series.css        # Shared design system
│   └── img/                  # Hero images, og card
├── _cache/                   # Local cache of Airtable bodies (gitignored)
├── _redirects                # Netlify routing
├── netlify.toml              # Netlify config
└── build.py                  # Regenerates parts 1–5 from Airtable
```

## Regenerating the essay pages

```bash
export AIRTABLE_API_KEY=pat...
python3 build.py
```

`build.py` will:

1. Fetch each of the 6 records by ID from Airtable (heavy long-form
   field, so one record at a time).
2. Cache each body to `_cache/partN.txt` and metadata to
   `_cache/partN.json` for inspection and offline rebuilds.
3. Re-render `/part-1/index.html` through `/part-5/index.html` from
   a single template.
4. Auto-detect hero images at `/assets/img/part-N-hero.jpg` and emit
   the right anchor markup. If absent, the anchor falls back to a
   type-only treatment.
5. Leave `/index.html` (the landing page) alone — it is hand-curated.

If `AIRTABLE_API_KEY` is not set, `build.py` falls back to whatever is
already in `_cache/` so the site can be re-rendered offline.

## Hero images

Anchor images do not exist yet. The Midjourney prompts are in the
Airtable records (field `fldNuHIx9TOXcxtsA`). When YC drops images
into `assets/img/part-N-hero.jpg` (1536×768, JPEG, dark/moody), re-run
`build.py` and the anchor banners will swap from type-only to
image-with-overlay automatically.

Open Graph share card lives at `assets/img/og-card.jpg` (1200×630).

## Deploying

**Do not deploy without explicit go-ahead from YC.** When ready:

```bash
netlify deploy --dir=. --prod
```

Or drag the folder to Netlify.

## Design

Calm copper + deep brown palette, EB Garamond body, Cormorant Garamond
display, Jost sans for UI chrome. Mobile-first responsive. Essay pages
swap the copper accent for red (`body.cadence-essay`) to distinguish
individual pieces from the series landing.

All design tokens live as CSS custom properties in
`assets/css/series.css`.
