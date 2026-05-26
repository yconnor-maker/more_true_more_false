#!/usr/bin/env python3
"""
fetch_heroes.py — download the Images attachments from Airtable and write
them into assets/img/ at the right sizes/filenames for the site.

Run this on your laptop (not in the cloud sandbox — the Airtable CDN is
host-restricted and won't serve from elsewhere).

Requires: pip install Pillow requests
   AIRTABLE_API_KEY=patXXX  python3 fetch_heroes.py

Then re-run `python3 build.py` so the anchor banners upgrade from
type-only to image-with-overlay.
"""
from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dep: pip install requests Pillow")
try:
    from PIL import Image
except ImportError:
    sys.exit("Missing dep: pip install Pillow")

BASE_ID = "appi63sF9wC7M0lbM"
TABLE_ID = "tbltPNwJpIszoBiCc"
IMAGES_FIELD = "fldCO6JB58OgNnTmp"  # "Images" multipleAttachments field

# (record_id, output filename, target (w, h))
TARGETS = [
    ("reclX6lcg0JYejlNV", "og-card.jpg",     (1200, 630)),  # Part 0 / landing → og
    ("recZg9XekID7WKKRE", "part-1-hero.jpg", (1536, 768)),
    ("recKpddZgNkam1LFu", "part-2-hero.jpg", (1536, 768)),
    ("recdAwIsINMWuh0EA", "part-3-hero.jpg", (1536, 768)),
    ("reciRclOeQEFBOk5J", "part-4-hero.jpg", (1536, 768)),
    ("recK0b1gFZQMuTnPd", "part-5-hero.jpg", (1536, 768)),
]


def fit_cover(img: Image.Image, tw: int, th: int) -> Image.Image:
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def main() -> int:
    token = os.environ.get("AIRTABLE_API_KEY") or os.environ.get("AIRTABLE_TOKEN")
    if not token:
        sys.exit("Set AIRTABLE_API_KEY (or AIRTABLE_TOKEN) and re-run.")

    out_dir = Path(__file__).resolve().parent / "assets" / "img"
    out_dir.mkdir(parents=True, exist_ok=True)

    for rec_id, fname, size in TARGETS:
        print(f"  {rec_id} → {fname} ({size[0]}×{size[1]})", end=" ", flush=True)

        # Fetch the record. Airtable returns fresh signed URLs each time.
        r = requests.get(
            f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}/{rec_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        fields = r.json().get("fields", {})
        atts = fields.get("Images") or []
        if not atts:
            print("⚠ no attachment on this record")
            continue

        url = atts[0]["url"]
        ir = requests.get(url, timeout=60)
        ir.raise_for_status()

        img = Image.open(BytesIO(ir.content)).convert("RGB")
        out = fit_cover(img, *size)
        dest = out_dir / fname
        out.save(dest, "JPEG", quality=85, optimize=True, progressive=True)
        kb = dest.stat().st_size / 1024
        print(f"src={img.size} → {kb:.0f}KB ✓")

    print("\nNow run: python3 build.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
