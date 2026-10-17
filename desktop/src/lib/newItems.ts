import type { Release } from "./types";

const SEEN_LIMIT = 500;

/** Itens que ainda não estavam na lista de vistos (novidades do radar). */
export function detectNew(seen: string[], items: Release[]): Release[] {
  const known = new Set(seen);
  return items.filter((item) => !known.has(item.id));
}

/** Mantém os ids mais recentes primeiro, sem repetição e com limite de memória. */
export function mergeSeen(seen: string[], items: Release[], limit = SEEN_LIMIT): string[] {
  const merged = [...items.map((item) => item.id), ...seen];
  return [...new Set(merged)].slice(0, limit);
}
