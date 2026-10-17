import { describe, expect, test } from "bun:test";
import { countByKind, EMPTY_FILTERS, filterReleases } from "./filters";
import type { Release } from "./types";

function item(partial: Partial<Release>): Release {
  return {
    id: "x",
    source: "youtube",
    kind: "video",
    title: "Título",
    url: "https://example.test",
    channel: "Canal",
    category: "games",
    thumbnail: null,
    summary: "",
    release_window: "",
    release_date: "",
    availability: "upcoming",
    why_it_matters: "",
    platforms: [],
    posted_at: null,
    ...partial,
  };
}

const items: Release[] = [
  item({ id: "1", kind: "video", category: "movies", title: "Trailer de Ação", channel: "KinoCheck" }),
  item({ id: "2", kind: "article", category: "games", title: "Anúncio de Jogo", channel: "PlayStation" }),
  item({ id: "3", kind: "catalog", category: "anime", title: "Anime Novo", availability: "released" }),
];

describe("filterReleases", () => {
  test("sem filtros devolve tudo", () => {
    expect(filterReleases(items, EMPTY_FILTERS)).toHaveLength(3);
  });

  test("filtra por tipo, categoria e disponibilidade", () => {
    expect(filterReleases(items, { ...EMPTY_FILTERS, kind: "article" }).map((i) => i.id)).toEqual(["2"]);
    expect(filterReleases(items, { ...EMPTY_FILTERS, category: "anime" }).map((i) => i.id)).toEqual(["3"]);
    expect(
      filterReleases(items, { ...EMPTY_FILTERS, availability: "released" }).map((i) => i.id),
    ).toEqual(["3"]);
  });

  test("busca ignora acentos e casa com canal e categoria traduzida", () => {
    expect(filterReleases(items, { ...EMPTY_FILTERS, query: "acao" }).map((i) => i.id)).toEqual(["1"]);
    expect(filterReleases(items, { ...EMPTY_FILTERS, query: "filmes" }).map((i) => i.id)).toEqual(["1"]);
    expect(filterReleases(items, { ...EMPTY_FILTERS, query: "playstation" }).map((i) => i.id)).toEqual(["2"]);
  });

  test("combina filtros", () => {
    expect(
      filterReleases(items, { kind: "article", category: "movies", availability: "all", query: "" }),
    ).toHaveLength(0);
  });
});

describe("countByKind", () => {
  test("conta por tipo", () => {
    expect(countByKind(items, "video")).toBe(1);
    expect(countByKind(items, "catalog")).toBe(1);
  });
});
