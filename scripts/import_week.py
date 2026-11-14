"""Copy saved Firecrawl scrapes of week-ahead SportyBet list pages into data/raw/<day>/week/."""
import glob
import json
import re
import sys
from pathlib import Path

src, day = sys.argv[1], sys.argv[2]
out = Path("data/raw") / day / "week"
out.mkdir(parents=True, exist_ok=True)
for f in glob.glob(src + "/*.txt"):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    url = d.get("metadata", {}).get("sourceURL", "")
    if "pcUpcomingEvents" not in url or "timeline=168" not in url:
        continue
    raw = d["rawHtml"]
    j = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    sport = "football" if "sport%3A1&" in url else "basketball"
    page = re.search(r"pageNum=(\d+)", url).group(1)
    (out / f"{sport}_p{page}.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")

for sport in ("football", "basketball"):
    ids, total, pages = set(), None, []
    for p in sorted(out.glob(f"{sport}_p*.json"), key=lambda p: int(p.stem.split("_p")[1])):
        j = json.loads(p.read_text(encoding="utf-8"))
        total = j.get("data", {}).get("totalNum", total)
        evs = [e["eventId"] for t in j.get("data", {}).get("tournaments", []) for e in t["events"]]
        pages.append((p.stem, len(evs)))
        ids.update(evs)
    print(sport, "total", total, "have", len(ids), pages)
