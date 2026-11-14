"""Command line: python -m jakita <command> ...

  predict     fetch (or read snapshot), model and write data/predictions/<day>.json
  render      turn a predictions file into a standalone HTML report
  import-har  load SportyBet responses from a Chrome DevTools HAR export
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from .config import EAT, REPORTS


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="jakita")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("predict")
    p.add_argument("--day", default=dt.datetime.now(EAT).date().isoformat(), help="data folder / label (YYYY-MM-DD)")
    p.add_argument("--sports", default="football,basketball")
    p.add_argument("--leagues", default="", help="comma list of substrings, e.g. 'Nations League,NBA' (default: top leagues)")
    p.add_argument("--teams", default="")
    p.add_argument("--dates", default="", help="comma list of EAT dates to include (default: day and day+1)")
    p.add_argument("--transport", default="snapshot", choices=["snapshot", "http", "firecrawl"])
    p.add_argument("--max-full", type=int, default=40, help="fixtures that also get their full market book")
    p.add_argument("--pages", type=int, default=20)
    p.add_argument("--days-ahead", type=int, default=7, help="prediction window in days (1-7)")

    r = sub.add_parser("render")
    r.add_argument("--day", default=dt.datetime.now(EAT).date().isoformat())
    r.add_argument("--out", default="")

    s = sub.add_parser("research", help="collect previews/tipsters for selected fixtures")
    s.add_argument("--day", default=dt.datetime.now(EAT).date().isoformat())
    s.add_argument("--sports", default="football")
    s.add_argument("--leagues", default="")
    s.add_argument("--transport", default="snapshot", choices=["snapshot", "http", "firecrawl"])
    s.add_argument("--max-events", type=int, default=15)
    s.add_argument("--no-llm", action="store_true")

    rs = sub.add_parser("results", help="fetch final scores for a day's predicted events, settle bets, evaluate")
    rs.add_argument("--day", default=dt.datetime.now(EAT).date().isoformat())
    rs.add_argument("--transport", default="http", choices=["snapshot", "http", "firecrawl"])

    rset = sub.add_parser("result-set", help="enter a final score by hand")
    rset.add_argument("event_id")
    rset.add_argument("ft", help="full-time score h:a")
    rset.add_argument("--ht", default=None, help="half-time score h:a")

    sub.add_parser("evaluate", help="settle open bets and recompute performance/calibration")

    h = sub.add_parser("import-har")
    h.add_argument("har")
    h.add_argument("--day", default=dt.datetime.now(EAT).date().isoformat())

    a = ap.parse_args(argv)
    if a.cmd == "predict":
        from .pipeline import run, save
        from .sources.sportybet import SportyBet, make_transport

        d0 = dt.date.fromisoformat(a.day)
        ahead = max(1, min(7, a.days_ahead))
        dates = [dt.date.fromisoformat(x) for x in a.dates.split(",") if x] or [d0 + dt.timedelta(days=i) for i in range(ahead + 1)]
        client = SportyBet(make_transport(a.transport, a.day), a.day)
        pred = run(client, a.day, [s for s in a.sports.split(",") if s],
                   [x.strip() for x in a.leagues.split(",") if x.strip()] or None, dates,
                   [x.strip() for x in a.teams.split(",") if x.strip()] or None, a.max_full, a.pages,
                   hours=168 if ahead > 2 else 48)
        path = save(pred, a.day)
        n = sum(len(s["events"]) for s in pred["sports"].values())
        print(f"wrote {path} ({n} events)")
    elif a.cmd == "render":
        from .render import render

        out = Path(a.out) if a.out else REPORTS / f"{a.day}.html"
        print(f"wrote {render(a.day, out)}")
    elif a.cmd == "research":
        from .config import TOP_LEAGUES
        from .sources.research import collect
        from .sources.sportybet import SportyBet, make_transport, select

        client = SportyBet(make_transport(a.transport, a.day), a.day)
        d0 = dt.date.fromisoformat(a.day)
        chosen = []
        for sport in a.sports.split(","):
            leagues = [x.strip() for x in a.leagues.split(",") if x.strip()] or TOP_LEAGUES[sport]
            chosen += select(client.fixtures(sport), leagues, [d0, d0 + dt.timedelta(days=1)])
        notes = collect(chosen[: a.max_events], a.day, use_llm=not a.no_llm)
        print(f"research notes for {len(notes)} fixtures")
    elif a.cmd in ("results", "result-set", "evaluate"):
        from . import tracker

        if a.cmd == "results":
            from .sources.sportybet import SportyBet, make_transport

            n = tracker.fetch_results(SportyBet(make_transport(a.transport, a.day), a.day, save=False), a.day)
            print(f"{n} new results")
        elif a.cmd == "result-set":
            tracker.set_result(a.event_id, a.ft, a.ht)
        print(f"settled {tracker.settle_bets()} bets")
        perf = tracker.evaluate()
        for fam, v in perf.items():
            print(f"  {fam:16s} n={v['n']:5d} brier={v['brier']} hit(fav)={v['hit_rate_fav']} roi(fav)={v['roi_fav']}")
    elif a.cmd == "import-har":
        from .sources.sportybet import import_har

        print(f"imported {import_har(Path(a.har), a.day)} responses")
