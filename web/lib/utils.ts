import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const pct = (p?: number | null) => (p == null ? "–" : `${Math.round(p * 100)}%`);
export const ev = (x: number) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%`;
