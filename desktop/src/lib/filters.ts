import { CATEGORY_LABELS, normalize } from "./format";
import type { Release } from "./types";

export interface Filters {
  kind: "all" | Release["kind"];
  category: string;
  availability: "all" | Release["availability"];
  query: string;
}

export const EMPTY_FILTERS: Filters = {
  kind: "all",
  category: "all",
  availability: "all",
  query: "",
};

/** Mesma regra de filtro/ordenação do painel web, sem tocar no DOM. */
export function filterReleases(items: Release[], filters: Filters): Release[] {
  const query = normalize(filters.query.trim());
  return items.filter((item) => {
    if (filters.kind !== "all" && item.kind !== filters.kind) return false;
    if (filters.category !== "all" && item.category !== filters.category) return false;
    if (filters.availability !== "all" && (item.availability || "unconfirmed") !== filters.availability)
      return false;
    if (!query) return true;
    const haystack = normalize(
      `${item.title} ${item.channel ?? ""} ${CATEGORY_LABELS[item.category] ?? item.category}`,
    );
    return haystack.includes(query);
  });
}

export function countByKind(items: Release[], kind: Release["kind"]): number {
  return items.filter((item) => item.kind === kind).length;
}
