"""Team crests and league flags.

* Team crests: Sportradar's public crest CDN, keyed by the `sr:competitor:<id>` that SportyBet
  uses for every team. Blank placeholders (tiny GIFs) are detected and skipped.
* League icons: the country flag of the league's SportyBet category (flagcdn.com), with
  neutral glyphs for international / club-international competitions (drawn in the UI).

`build_sprites` downloads (cached under data/icons/) and packs everything into two sprite
sheets plus an index, so a static page can show thousands of icons from two image files.
"""
from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from .config import DATA

CREST_URL = "https://img.sportradar.com/ls/crest/big/{id}.png"
FLAG_URL = "https://flagcdn.com/w80/{code}.png"
CACHE = DATA / "icons"
UA = {"User-Agent": "jakita/0.1 (sports-prediction research)"}

# SportyBet category name -> ISO 3166 / flagcdn code. Unlisted names get no flag.
FLAGS = {
    "England": "gb-eng", "Scotland": "gb-sct", "Wales": "gb-wls", "Northern Ireland": "gb-nir", "Ireland": "ie",
    "Spain": "es", "Italy": "it", "Germany": "de", "France": "fr", "Netherlands": "nl", "Portugal": "pt", "Belgium": "be",
    "Turkiye": "tr", "Greece": "gr", "Austria": "at", "Switzerland": "ch", "Denmark": "dk", "Sweden": "se", "Norway": "no",
    "Finland": "fi", "Iceland": "is", "Poland": "pl", "Czechia": "cz", "Slovakia": "sk", "Hungary": "hu", "Romania": "ro",
    "Bulgaria": "bg", "Serbia": "rs", "Croatia": "hr", "Slovenia": "si", "Bosnia and Herzegovina": "ba", "Montenegro": "me",
    "North Macedonia": "mk", "Albania": "al", "Kosovo": "xk", "Cyprus": "cy", "Malta": "mt", "Luxembourg": "lu",
    "Ukraine": "ua", "Russia": "ru", "Belarus": "by", "Georgia": "ge", "Armenia": "am", "Azerbaijan": "az", "Israel": "il",
    "Latvia": "lv", "Lithuania": "lt", "Estonia": "ee", "Moldova": "md", "Kazakhstan": "kz", "Uzbekistan": "uz",
    "Brazil": "br", "Argentina": "ar", "Uruguay": "uy", "Paraguay": "py", "Chile": "cl", "Peru": "pe", "Bolivia": "bo",
    "Ecuador": "ec", "Colombia": "co", "Venezuela": "ve", "Mexico": "mx", "USA": "us", "Canada": "ca", "Costa Rica": "cr",
    "Guatemala": "gt", "Honduras": "hn", "El Salvador": "sv", "Panama": "pa", "Jamaica": "jm", "Puerto Rico": "pr",
    "Nicaragua": "ni", "Dominican Republic": "do",
    "Japan": "jp", "Republic of Korea": "kr", "China": "cn", "Chinese Taipei": "tw", "Hong Kong, China": "hk",
    "India": "in", "Indonesia": "id", "Thailand": "th", "Vietnam": "vn", "Malaysia": "my", "Singapore": "sg",
    "Australia": "au", "New Zealand": "nz", "Saudi Arabia": "sa", "United Arab Emirates": "ae", "Qatar": "qa",
    "Bahrain": "bh", "Kuwait": "kw", "Oman": "om", "Iran": "ir", "Iraq": "iq", "Jordan": "jo",
    "Egypt": "eg", "Morocco": "ma", "Tunisia": "tn", "Algeria": "dz", "Nigeria": "ng", "Ghana": "gh", "Kenya": "ke",
    "Tanzania": "tz", "Uganda": "ug", "South Africa": "za", "Cameroon": "cm", "Senegal": "sn", "Mali": "ml",
    "Ivory Coast": "ci", "Zambia": "zm", "Ethiopia": "et", "Rwanda": "rw",
}


def category_of(league: str) -> str:
    return league.split(" | ")[0].replace(" Amateur", "").strip()


def flag_code(league: str) -> str | None:
    return FLAGS.get(category_of(league))


def league_kind(league: str) -> str:
    """'flag' | 'intl' | 'clubs' | 'youth' | 'other' - lets the UI draw a glyph when there is no flag."""
    c = league.split(" | ")[0]
    if flag_code(league):
        return "flag"
    return {"International": "intl", "International Clubs": "clubs", "International Youth": "youth"}.get(c, "other")


def crest_url(competitor_id: str | None) -> str | None:
    if not competitor_id:
        return None
    return CREST_URL.format(id=competitor_id.split(":")[-1])


def _fetch(url: str, path: Path) -> Path | None:
    if path.exists():
        return path if path.stat().st_size > 200 else None
    try:
        r = requests.get(url, headers=UA, timeout=20)
    except requests.RequestException:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = r.status_code == 200 and "png" in r.headers.get("content-type", "") and len(r.content) > 200
    path.write_bytes(r.content if ok else b"")  # cache misses too
    return path if ok else None


def build_sprites(team_ids: set[str], leagues: set[str], out: Path, size: int = 48) -> dict:
    """Return {"crests": {competitor_id: index}, "flags": {code: index}, "size": size, "cols": cols}."""
    from PIL import Image

    jobs = {cid: (crest_url(cid), CACHE / "crests" / f"{cid.split(':')[-1]}.png") for cid in team_ids}
    codes = {flag_code(l) for l in leagues} - {None}
    fjobs = {c: (FLAG_URL.format(code=c), CACHE / "flags" / f"{c}.png") for c in codes}
    with ThreadPoolExecutor(8) as ex:
        got = dict(zip(jobs, ex.map(lambda v: _fetch(*v), jobs.values())))
        fgot = dict(zip(fjobs, ex.map(lambda v: _fetch(*v), fjobs.values())))

    def sheet(items: dict, w: int, h: int, name: str) -> dict:
        items = {k: p for k, p in items.items() if p}
        cols = 40
        rows = max(1, -(-len(items) // cols))
        img = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
        idx = {}
        for i, (k, p) in enumerate(sorted(items.items())):
            try:
                im = Image.open(io.BytesIO(p.read_bytes())).convert("RGBA")
            except Exception:
                continue
            im.thumbnail((w, h), Image.LANCZOS)
            img.paste(im, ((i % cols) * w + (w - im.width) // 2, (i // cols) * h + (h - im.height) // 2), im)
            idx[k] = i
        out.mkdir(parents=True, exist_ok=True)
        img.save(out / name, "WEBP", quality=80, method=6)
        return {"index": idx, "cols": cols, "w": w, "h": h, "file": name}

    meta = {"crests": sheet(got, size, size, "crests.webp"), "flags": sheet(fgot, 32, 24, "flags.webp")}
    (out / "icons.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta
