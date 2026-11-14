import { Globe2, Layers, Star, Trophy } from "lucide-react";

/* League icon: the country flag of the league (flagcdn), or a glyph for international competitions. */
export function LeagueFlag({ flag, kind, className = "" }: { flag?: string | null; kind?: string; className?: string }) {
  if (flag) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={`https://flagcdn.com/w40/${flag}.png`} alt="" width={20} height={15} loading="lazy" className={`h-[15px] w-5 shrink-0 rounded-[3px] object-cover ring-1 ring-black/20 ${className}`} />;
  }
  const Icon = kind === "intl" ? Globe2 : kind === "clubs" ? Trophy : kind === "youth" ? Star : Layers;
  return <Icon className={`size-4 shrink-0 text-muted-foreground ${className}`} aria-hidden />;
}
