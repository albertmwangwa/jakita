from __future__ import annotations

import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
RESEARCH = DATA / "research"
PREDICTIONS = DATA / "predictions"
REPORTS = ROOT / "reports"

# SportyBet Tanzania; all user-facing times are East Africa Time.
COUNTRY = "tz"
EAT = dt.timezone(dt.timedelta(hours=3), "EAT")

SPORTS = {
    "football": {"id": "sr:sport:1", "list_markets": "1,18,29,10"},
    "basketball": {"id": "sr:sport:2", "list_markets": "219,225,223"},
}

# Tournaments treated as "top" when no explicit filter is given (substring match on
# "<category> | <tournament>").
TOP_LEAGUES = {
    "football": [
        "International | UEFA Nations League", "International | Int. Friendly Games",
        "International | Africa Cup of Nations Qualification", "International | CONCACAF Nations League",
        "International | World Cup", "International Clubs | UEFA Champions League",
        "International Clubs | UEFA Europa League", "International Clubs | UEFA Conference League",
        "England | Premier League", "England | Championship", "Spain | LaLiga", "Spain | LALIGA HYPERMOTION",
        "Italy | Serie A", "Germany | Bundesliga", "France | Ligue 1", "Netherlands | Eredivisie",
        "Portugal | Liga Portugal", "Brazil | Brasileiro Serie A", "Mexico | Liga MX", "USA | MLS",
        "Argentina | Primera LPF", "Turkiye | Super Lig", "Saudi Arabia | Saudi Pro League",
        "Japan | J.League Cup", "Japan | J1 League",
    ],
    "basketball": [
        "USA | NBA", "International | Euroleague", "International | Eurocup", "Spain | Liga ACB",
        "Turkiye | Super Lig", "Greece | Basketball League", "Germany | BBL", "Italy | Serie A",
        "France | LNB Elite", "International | Liga ABA",
    ],
}

# Market families never turned into picks (player props, novelty).
EXCLUDED_GROUPS = {"Players"}
MIN_ODDS = 1.15
