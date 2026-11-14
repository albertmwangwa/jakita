"""SportyBet (TZ) fixtures and full market books.

The public site loads its data from JSON endpoints under /api/{country}/factsCenter/.
Three interchangeable transports fetch them:

* ``http``      - plain HTTPS (works from networks SportyBet serves, e.g. Tanzania)
* ``firecrawl`` - via the Firecrawl scrape API (set FIRECRAWL_API_KEY)
* ``snapshot``  - offline: files previously saved under data/raw/<date>/ (including ones
                  imported from a Chrome DevTools HAR export with ``jakita import-har``)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlencode

import requests

from ..config import COUNTRY, EAT, RAW, SPORTS

BASE = f"https://www.sportybet.com/api/{COUNTRY}/factsCenter"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def list_url(sport: str, page: int, hours: int = 48, page_size: int = 100) -> str:
    q = {"sportId": SPORTS[sport]["id"], "marketId": SPORTS[sport]["list_markets"], "pageSize": page_size,
         "pageNum": page, "option": 1, "timeline": hours}
    return f"{BASE}/pcUpcomingEvents?{urlencode(q)}"


def event_url(event_id: str) -> str:
    return f"{BASE}/event?eventId={quote(event_id)}&productId=3"


def _json_from(text: str) -> dict:
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


class HttpTransport:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/json",
                               "Referer": f"https://www.sportybet.com/{COUNTRY}/"})

    def get(self, url: str) -> dict:
        r = self.s.get(url, timeout=30)
        r.raise_for_status()
        return _json_from(r.text)


class FirecrawlTransport:
    def __init__(self, api_key: str | None = None):
        self.key = api_key or os.environ.get("FIRECRAWL_API_KEY")
        if not self.key:
            raise RuntimeError("FIRECRAWL_API_KEY is not set")

    def get(self, url: str) -> dict:
        for endpoint in ("https://api.firecrawl.dev/v2/scrape", "https://api.firecrawl.dev/v1/scrape"):
            r = requests.post(endpoint, headers={"Authorization": f"Bearer {self.key}"},
                              json={"url": url, "formats": ["rawHtml"], "maxAge": 0}, timeout=90)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            return _json_from(r.json()["data"]["rawHtml"])
        raise RuntimeError("Firecrawl scrape endpoint not found")


class SnapshotTransport:
    def __init__(self, day: str):
        self.dir = RAW / day

    def get(self, url: str) -> dict:
        if "/event?" in url:
            eid = re.search(r"eventId=([^&]+)", url).group(1).split("%3A")[-1].split(":")[-1]
            p = self.dir / "events" / f"{eid}.json"
        else:
            sport = "football" if "sport%3A1&" in url or "sport:1&" in url else "basketball"
            page = re.search(r"pageNum=(\d+)", url).group(1)
            hours = int((re.search(r"timeline=(\d+)", url) or [0, "48"])[1])
            p = self.dir / "week" / f"{sport}_p{page}.json" if hours > 48 else self.dir / f"{sport}_list_p{page}.json"
        if not p.exists():
            raise FileNotFoundError(p)
        return json.loads(p.read_text(encoding="utf-8"))


def make_transport(name: str, day: str):
    return {"http": HttpTransport, "firecrawl": FirecrawlTransport}.get(name, lambda: SnapshotTransport(day))()


class SportyBet:
    def __init__(self, transport, day: str, save: bool = True):
        self.t, self.day, self.save = transport, day, save
        (RAW / day / "events").mkdir(parents=True, exist_ok=True)
        (RAW / day / "week").mkdir(parents=True, exist_ok=True)

    def _store(self, rel: str, payload: dict) -> None:
        if self.save and not isinstance(self.t, SnapshotTransport):
            (RAW / self.day / rel).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def fixtures(self, sport: str, max_pages: int = 3, hours: int = 48) -> list[dict]:
        events: list[dict] = []
        for page in range(1, max_pages + 1):
            try:
                j = self.t.get(list_url(sport, page, hours))
            except FileNotFoundError:
                break
            self._store(f"week/{sport}_p{page}.json" if hours > 48 else f"{sport}_list_p{page}.json", j)
            tours = j.get("data", {}).get("tournaments", [])
            if not tours:
                break
            for t in tours:
                events.extend(t.get("events", []))
            if not isinstance(self.t, SnapshotTransport):
                time.sleep(0.5)
        return events

    def event(self, event_id: str) -> dict | None:
        try:
            j = self.t.get(event_url(event_id))
        except FileNotFoundError:
            return None
        self._store(f"events/{event_id.split(':')[-1]}.json", j)
        return j.get("data")


def league_of(e: dict) -> str:
    c = e["sport"]["category"]
    return f"{c['name']} | {c['tournament']['name']}"


def kickoff(e: dict) -> dt.datetime:
    return dt.datetime.fromtimestamp(e["estimateStartTime"] / 1000, EAT)


def select(events: Iterable[dict], leagues: list[str] | None, days: list[dt.date] | None,
           teams: list[str] | None = None) -> list[dict]:
    out = []
    for e in events:
        if days and kickoff(e).date() not in days:
            continue
        lg = league_of(e)
        if leagues and not any(l.lower() in lg.lower() for l in leagues):
            continue
        if teams and not any(t.lower() in (e["homeTeamName"] + " " + e["awayTeamName"]).lower() for t in teams):
            continue
        out.append(e)
    return sorted(out, key=lambda e: e["estimateStartTime"])


def import_har(har_path: Path, day: str) -> int:
    """Extract SportyBet API responses from a Chrome DevTools HAR export into data/raw/<day>/."""
    har = json.loads(Path(har_path).read_text(encoding="utf-8"))
    n = 0
    (RAW / day / "events").mkdir(parents=True, exist_ok=True)
    for entry in har.get("log", {}).get("entries", []):
        url = entry["request"]["url"]
        text = entry.get("response", {}).get("content", {}).get("text")
        if "factsCenter" not in url or not text:
            continue
        try:
            j = _json_from(text)
        except ValueError:
            continue
        if "/event?" in url and j.get("data", {}).get("eventId"):
            eid = j["data"]["eventId"].split(":")[-1]
            (RAW / day / "events" / f"{eid}.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
            n += 1
        elif "pcUpcomingEvents" in url or "liveOrPrematchEvents" in url:
            sport = "football" if "sport%3A1" in url or "sport:1" in url else "basketball"
            page = (re.search(r"pageNum=(\d+)", url) or [None, "1"])[1]
            (RAW / day / f"{sport}_list_p{page}.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
            n += 1
    return n
