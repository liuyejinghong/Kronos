import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function compactLabel(value: string) {
  return value.replaceAll("_", " ");
}

export function scoreFromRank(rank: number) {
  return Math.max(8, 100 - (rank - 1) * 7);
}
