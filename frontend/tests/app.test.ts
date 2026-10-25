import { describe, it, expect, beforeEach, vi } from "vitest";
import { createApp, type ReleaseItem } from "../src/app";

const testItems: ReleaseItem[] = [
  {
    id: "item-1",
    title: "Filme Alpha",
    kind: "video",
    category: "movies",
    availability: "upcoming",
    url: "https://example.com/alpha",
    summary: "Resumo do filme alpha",
  },
  {
    id: "item-2",
    title: "Série Beta",
    kind: "article",
    category: "series",
    availability: "released",
    url: "https://example.com/beta",
    summary: "Resumo da série beta",
  },
  {
    id: "item-3",
    title: "Filme Gamma",
    kind: "catalog",
    category: "movies",
    availability: "upcoming",
    url: "https://example.com/gamma",
    summary: "Resumo do filme gamma",
  },
];

function setupDOM(): Document {
  document.body.innerHTML = `
    <h1 id="page-title">Título</h1>
    <p id="result-count" class="result-count" aria-live="polite" aria-atomic="true">Carregando…</p>
    <div class="tabs">
      <button type="button" class="tab active" data-kind="all" aria-pressed="true">Todos</button>
      <button type="button" class="tab" data-kind="video" aria-pressed="false">▶ YouTube</button>
      <button type="button" class="tab" data-kind="article" aria-pressed="false">↗ Artigos</button>
      <button type="button" class="tab" data-kind="catalog" aria-pressed="false">▣ Páginas oficiais</button>
    </div>
    <input id="search" type="search" />
    <select id="category">
      <option value="all">Todas</option>
      <option value="movies">Filmes</option>
      <option value="series">Séries</option>
      <option value="games">Jogos</option>
      <option value="anime">Animes</option>
    </select>
    <select id="availability">
      <option value="all">Todas</option>
      <option value="upcoming">Vai estrear</option>
      <option value="released">Já disponível</option>
      <option value="unconfirmed">A confirmar</option>
    </select>
    <select id="sort">
      <option value="recent">Mais recentes</option>
      <option value="soon">Estreia mais próxima</option>
    </select>
    <button id="reset-filters" type="button">Limpar filtros</button>
    <span id="updated-at"></span>
    <button id="refresh" type="button">Atualizar</button>
    <div id="status" role="status">
      <p id="status-text"></p>
      <button id="retry" type="button" hidden>Tentar novamente</button>
    </div>
    <div id="cards" class="cards"></div>
  `;
  return document;
}

describe("App frontend", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("typing 5 characters in less than 200 ms triggers 1 renderization", async () => {
    const doc = setupDOM();
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: testItems }),
    });

    const app = createApp(doc, { fetchImpl });
    await app.loadItems();

    const searchInput = doc.querySelector<HTMLInputElement>("#search")!;
    const cards = doc.querySelector<HTMLDivElement>("#cards")!;

    expect(cards.children.length).toBe(3);

    // Type 5 characters fast (< 200 ms total)
    const chars = ["a", "l", "p", "h", "a"];
    for (let i = 0; i < chars.length; i++) {
      searchInput.value = searchInput.value + chars[i];
      searchInput.dispatchEvent(new Event("input"));
      vi.advanceTimersByTime(30); // 30ms between keypresses = 150ms total
    }

    // Before timer reaches 200ms from last keypress, DOM is still showing initial 3 cards
    expect(cards.children.length).toBe(3);

    // Fast-forward remaining time (>200ms)
    vi.advanceTimersByTime(200);

    // Now debounce fired exactly once
    expect(cards.children.length).toBe(1);
    expect(cards.querySelector("h3")?.textContent).toBe("Filme Alpha");
  });

  it("preserves open <details> state when changing category filter", async () => {
    const doc = setupDOM();
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: testItems }),
    });

    const app = createApp(doc, { fetchImpl });
    await app.loadItems();

    const cards = doc.querySelector<HTMLDivElement>("#cards")!;
    const firstCardDetails = cards.querySelector<HTMLDetailsElement>("details")!;
    expect(firstCardDetails).not.toBeNull();

    // Open details on first card
    firstCardDetails.open = true;
    expect(firstCardDetails.open).toBe(true);

    // Change category select to 'movies' (which retains item-1 and item-3)
    const categorySelect = doc.querySelector<HTMLSelectElement>("#category")!;
    categorySelect.value = "movies";
    categorySelect.dispatchEvent(new Event("change"));

    // Verify first card details remains open
    const updatedCards = doc.querySelectorAll<HTMLElement>(".card");
    expect(updatedCards.length).toBe(2);
    const firstUpdatedCard = updatedCards[0];
    expect(firstUpdatedCard).toBeDefined();
    const updatedDetails = firstUpdatedCard!.querySelector<HTMLDetailsElement>("details")!;
    expect(updatedDetails).toBe(firstCardDetails); // same element instance
    expect(updatedDetails.open).toBe(true);
  });

  it("cancels search debounce timer and focuses #result-count on resetFilters", async () => {
    const doc = setupDOM();
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: testItems }),
    });

    const app = createApp(doc, { fetchImpl });
    await app.loadItems();

    const searchInput = doc.querySelector<HTMLInputElement>("#search")!;
    searchInput.value = "Alpha";
    searchInput.dispatchEvent(new Event("input"));

    // Reset filters before debounce finishes
    const resetButton = doc.querySelector<HTMLButtonElement>("#reset-filters")!;
    resetButton.click();

    const resultCount = doc.querySelector<HTMLElement>("#result-count")!;
    expect(doc.activeElement).toBe(resultCount);
    expect(searchInput.value).toBe("");

    // Advance timers to ensure cancelled debounce timer does not overwrite search reset
    vi.advanceTimersByTime(300);
    expect(searchInput.value).toBe("");
  });
});
