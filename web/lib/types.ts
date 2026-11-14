export type Pick = {
  label: string; mid: string; spec: string; desc: string; odds: number | null; p: number; ev: number | null;
  confidence: "High" | "Medium" | "Low"; why: string;
};

export type MarketRow = {
  mid: string; market: string; spec: string; desc: string; odds: number | null; fair: number | null;
  p: number; push?: number; ev: number | null;
};

export type Consensus = { market_id: string; spec: string; desc: string; votes: number; sources: string[]; avg_prob: number | null };

export type EventPrediction = {
  event_id: string; game_id?: string; sport: "football" | "basketball"; league: string; kickoff: string;
  home: string; away: string; venue?: string; home_icon?: string; away_icon?: string;
  flag?: string | null; league_kind?: "flag" | "intl" | "clubs" | "youth" | "other"; depth?: "full" | "model";
  coverage: { markets: number; outcomes: number; modeled: number };
  model: Record<string, any>;
  research: Record<string, any>;
  consensus: Consensus[];
  picks: { calls: Record<string, Pick | Pick[] | null>; safest: Pick[]; value: Pick[] };
  markets: MarketRow[];
};

export type Acca = { legs: (Pick & { match: string; kickoff: string })[]; odds: number; p: number } | null;

export type Bet = {
  id: string; event_id: string; sport: string; match: string; home: string; away: string; kickoff: string;
  home_icon?: string; away_icon?: string; label: string; mid: string; spec: string; desc: string; odds: number; p: number;
  stake: number; status: "open" | "won" | "lost" | "push" | "half_won" | "half_lost"; payout: number | null;
  placed_at: string; score?: string;
};

export type Performance = Record<string, { n: number; brier: number; hit_rate_fav: number | null; roi_fav: number | null; reliability: [number, number, number][] }>;

export type Predictions = {
  generated: string; day: string; timezone: string; source: string;
  sports: Record<string, { events: EventPrediction[]; accumulators: { safe: Acca; value: Acca }; fixtures_scanned: number }>;
  social?: { x_com?: string; x_posts?: { handle: string; fixture: string; pick: string }[] };
};
