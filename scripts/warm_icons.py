import json, glob, sys
from pathlib import Path
from jakita.icons import build_sprites
day = sys.argv[1]
teams, leagues = set(), set()
for f in glob.glob(f"data/raw/{day}/week/*.json") + glob.glob(f"data/raw/{day}/*_list_p*.json"):
    j = json.loads(Path(f).read_text(encoding="utf-8"))
    for t in j.get("data", {}).get("tournaments", []):
        for e in t["events"]:
            teams.update([e["homeTeamId"], e["awayTeamId"]])
            c = e["sport"]["category"]; leagues.add(f"{c['name']} | {c['tournament']['name']}")
meta = build_sprites(teams, leagues, Path(f"reports/assets"))
print("teams", len(teams), "crests", len(meta["crests"]["index"]), "leagues", len(leagues), "flags", len(meta["flags"]["index"]))
