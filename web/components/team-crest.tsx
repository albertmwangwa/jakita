"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

/* White crest circle (as in the mock) with the team's crest; initials only if no crest exists. */
export function TeamCrest({ name, icon, size = 56, className }: { name: string; icon?: string; size?: number; className?: string }) {
  const [failed, setFailed] = useState(false);
  const initials = name.replace(/\b(FC|SC|CF|BC|KK|AC|EC|CA|CD|SK)\b/g, "").trim().split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase();
  const inner = Math.round(size * 0.74);
  return (
    <span className={cn("inline-grid shrink-0 place-items-center overflow-hidden rounded-full bg-white text-zinc-900 ring-1 ring-black/5", className)}
      style={{ width: size, height: size }}>
      {icon && !failed
        // eslint-disable-next-line @next/next/no-img-element
        ? <img src={icon} alt="" width={inner} height={inner} loading="lazy" className="object-contain"
            onLoad={e => { if ((e.target as HTMLImageElement).naturalWidth <= 1) setFailed(true); }} onError={() => setFailed(true)} />
        : <span className="font-display font-bold" style={{ fontSize: Math.round(size * 0.3) }}>{initials}</span>}
    </span>
  );
}
