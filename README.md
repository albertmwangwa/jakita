# Jakita

Football and basketball predictions across every SportyBet (TZ) market: 1X2, goals, halves,
correct score, combos, handicaps, corners, cards, shots, team totals and more. The models are
anchored on the bookmaker's own full market book and adjusted with stats, team news and tipster
consensus.

## Pipeline

```
SportyBet fixtures (48h) ──► full market book per fixture (200–950 markets)
        │                              │ de-vig (power method)
        │                              ▼
        │                 fit models to main markets
        │                   • football: Dixon-Coles Poisson (λh, λa, ρ, 1st-half share)
        │                   • counts: negative binomial per O/U ladder (corners, cards, shots, fouls…)
        │                   • basketball: normal margin / total / team totals / halves
research (previews,  ──►  blend stat-model & tipster probabilities into the fit targets
lineups, injuries,        (12% per source, capped at 35%); corner/card averages into ladders
tipsters, X)              │
                          ▼
           reprice every outcome ─► P(win), P(push), EV vs actual odds
                          ▼
     calls per market family · strongest picks · value picks · accumulators
                          ▼
         data/predictions/<day>.json ─► HTML report / Next.js (shadcn) UI
```

## Quick start

```bash
pip install -r requirements.txt

# From a network SportyBet serves (Tanzania): every fixture in the next 7 days
python -m jakita predict --day 2026-11-15 --transport http
#   --days-ahead 1..7   window (default 7)
#   --max-full 40       how many top-league fixtures also get their full market book
#   --leagues "Premier League,NBA"   optional filter (substring on "Country | Tournament")

# Elsewhere: set FIRECRAWL_API_KEY and use --transport firecrawl, or export a HAR from
# Chrome DevTools (Network tab, on sportybet.com/tz) and import it:
python -m jakita import-har sportybet.har --day 2026-11-15
python -m jakita predict --day 2026-11-15 --transport snapshot

# Team news, lineups, tipsters (Firecrawl search + Claude extraction; --no-llm for regex only)
python -m jakita research --day 2026-11-15 --leagues "Premier League"

python -m jakita render --day 2026-11-15     # reports/2026-11-15.html

# After the games: fetch final scores, settle My Bets, score the model, train calibration
python -m jakita results --day 2026-11-15 --transport http
python -m jakita result-set sr:match:68932052 2:1 --ht 1:0   # manual entry if a feed lacks it
python -m jakita evaluate
```

`data/performance.json` keeps Brier score, hit rate and flat-stake ROI per market family.
Once a family has 200 settled prices, an isotonic calibration map (`data/calibration.json`)
is fitted and applied to new predictions, shrunk 50% toward the raw model.

Filters: `--sports football,basketball`, `--leagues` (substring match on "Country | Tournament";
default is the top-league list in `jakita/config.py`), `--teams`, `--dates`, `--max-events`, `--pages`.

### Coverage depths

* **Full book**: the headline fixtures (top leagues first, `--max-full`) get every SportyBet
  market priced, 200 to 950 per fixture, including corners, cards and shots.
* **Model**: every other fixture is fitted from the list feed's main markets (1X2, goal
  lines, BTTS, double chance). The goal model then prices about 100 derived selections:
  correct score, HT/FT, halves, team totals, combos, margins and multigoals. Where SportyBet
  doesn't quote one, the model's fair odds are shown instead.

### Icons

Team crests come from Sportradar's public crest CDN, keyed by the `sr:competitor:<id>` that
SportyBet uses for every team. League icons are country flags from flagcdn.com, and
international competitions get glyphs. `python -m scripts.warm_icons <day>` caches them and
builds the sprite sheets used by the static report.

## Web UI (`web/`)

Next.js 15 + shadcn/ui, Manrope (body) and Space Grotesk (display), in a dark sportsbook style.

* **Left sidebar:** sports, My Bets and Insights, the days of the week, and every league
  grouped by country with its flag. Leagues are searchable.
* **Fixtures:** cards with team crests, predicted score and 1 / X / 2 pills. Opening one loads its
  full detail (`/api/event`): calls, the Performance grid, team news and every priced market.
  "Make Bet" adds the pick to My Bets.
* **My Bets:** WIN / LOSE cards, profit and loss, and the model track record.
* **Insights:** crowd versus model for every collected tip.
* **+ button:** calls `POST /api/run`, which runs `research → predict → render`.

```bash
cd web && npm install && npm run dev      # http://localhost:3000
```

Environment: `JAKITA_ROOT` (repo path), `JAKITA_PYTHON` (python executable),
`FIRECRAWL_API_KEY`, `ANTHROPIC_API_KEY` (or `ant auth login`).

## Layout

| Path | What |
|---|---|
| `jakita/sources/sportybet.py` | fixtures + full books; http / firecrawl / snapshot transports; HAR import |
| `jakita/sources/research.py` | preview search, Claude structured extraction, merge into `data/research/<day>.json` |
| `jakita/markets.py` | market parsing and de-vig |
| `jakita/models/football.py` | goal model + pricing of ~50 goal-market families |
| `jakita/models/counts.py` | corners / cards / shots / fouls / offsides |
| `jakita/models/basketball.py` | margin / totals / team totals / halves / winning margin |
| `jakita/consensus.py` | tipster pick aggregation (sentiment) |
| `jakita/pipeline.py` | orchestration, picks, accumulators |
| `jakita/render.py`, `templates/report.html` | standalone report |
| `data/raw/<day>/` | raw SportyBet JSON snapshots |

## Roadmap

1. **Stat-based settlement**: corners/cards results so those families get tracked too.
2. **Independent stats model**: team ratings (Elo / xG-based) from historical results, blended
   with the market fit, so edges don't rely only on outside tipsters.
3. **More books**: compare SportyBet with other bookmakers' prices for line shopping and sharper anchors.
4. **Lineup triggers**: re-run when confirmed XIs drop (~60 min before kick-off).
5. **Scheduling**: a daily morning run and a pre-kick-off refresh.
