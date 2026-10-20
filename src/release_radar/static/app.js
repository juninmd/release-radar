const kindLabels = {
    video: "YouTube",
    article: "Artigo",
    catalog: "Página oficial",
};
// Rotulo do que o video e de fato: trailer de lancamento nunca se mistura com clipe.
const contentLabels = {
    trailer: "Trailer",
    teaser: "Teaser",
    announcement: "Anúncio",
    video: "Vídeo",
};
const FRESH_MS = 48 * 60 * 60 * 1000;
const categoryLabels = {
    movies: "Filmes",
    series: "Séries",
    games: "Jogos",
    anime: "Animes",
};
const availabilityLabels = {
    upcoming: "Vai estrear",
    released: "Já disponível",
    unconfirmed: "A confirmar",
};
const linkActions = {
    video: "Assistir",
    article: "Ler artigo",
    catalog: "Ver página",
};
const placeholderWindow = /^(desconhecid[oa]|a definir|unknown)$/i;
const isoDate = /^\d{4}-\d{2}-\d{2}$/;
function isOneOf(value, options) {
    return typeof value === "string" && options.includes(value);
}
export function isLinkKind(value) {
    return isOneOf(value, Object.keys(kindLabels));
}
export function isCategory(value) {
    return isOneOf(value, Object.keys(categoryLabels));
}
export function isAvailability(value) {
    return isOneOf(value, Object.keys(availabilityLabels));
}
export function isTabKind(value) {
    return value === "all" || isLinkKind(value);
}
export function isReleasesResponse(value) {
    return (typeof value === "object" &&
        value !== null &&
        Array.isArray(value.items));
}
export function safeUrl(value) {
    if (typeof value !== "string" || value === "")
        return null;
    try {
        const url = new URL(value);
        return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password
            ? url.href
            : null;
    }
    catch {
        return null;
    }
}
export function normalize(value) {
    return String(value ?? "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLocaleLowerCase("pt-BR");
}
export function categoryLabel(category) {
    return isCategory(category) ? categoryLabels[category] : category;
}
export function resolveAvailability(value) {
    return isAvailability(value) ? value : "unconfirmed";
}
export function releaseWindow(item) {
    const value = String(item.release_date || item.release_window || "").trim();
    if (!value || placeholderWindow.test(value))
        return "Data a confirmar";
    if (isoDate.test(value)) {
        const date = new Date(`${value}T12:00:00Z`);
        if (!Number.isNaN(date.valueOf()) &&
            date.toISOString().slice(0, 10) === value) {
            return new Intl.DateTimeFormat("pt-BR", {
                dateStyle: "medium",
                timeZone: "UTC",
            }).format(date);
        }
    }
    return value;
}
export function isFresh(item, nowMs = Date.now()) {
    const posted = Date.parse(item.posted_at ?? "");
    return Number.isFinite(posted) && nowMs - posted < FRESH_MS;
}
export function sortByNearestPremiere(items) {
    const day = (item) => resolveAvailability(item.availability) === "upcoming" && isoDate.test(item.release_date ?? "")
        ? item.release_date
        : "9999-99-99";
    return [...items].sort((a, b) => day(a).localeCompare(day(b)));
}
export function filterItems(items, filters) {
    const query = normalize(filters.query.trim());
    return items.filter((item) => (filters.kind === "all" || item.kind === filters.kind) &&
        (filters.category === "all" || item.category === filters.category) &&
        (filters.availability === "all" ||
            resolveAvailability(item.availability) === filters.availability) &&
        normalize(`${item.title} ${item.channel ?? ""} ${categoryLabel(item.category)}`).includes(query));
}
export function countLabel(visibleCount, totalCount, state) {
    if (state.hasLoaded) {
        return `${visibleCount} de ${totalCount} ${totalCount === 1 ? "link" : "links"}`;
    }
    return state.isLoading ? "Carregando…" : "Indisponível";
}
export function statusMessage(state, counts) {
    if (state.loadError) {
        return "Não foi possível carregar os links. Tente novamente; seus filtros serão mantidos.";
    }
    if (state.isLoading && !state.hasLoaded)
        return "Buscando novidades…";
    if (counts.visible > 0)
        return null;
    return counts.total
        ? "Nada por aqui com esses filtros. Tente outra busca ou use Limpar filtros."
        : "Ainda não há lançamentos publicados. As próximas descobertas aparecerão aqui.";
}
export function detailParagraph(title, text, doc = document) {
    const section = doc.createElement("div");
    const heading = doc.createElement("h4");
    heading.textContent = title;
    const paragraph = doc.createElement("p");
    paragraph.textContent = text;
    section.append(heading, paragraph);
    return section;
}
export function makeCard(item, doc = document) {
    const article = doc.createElement("article");
    article.className = "card";
    const thumb = doc.createElement("div");
    thumb.className = "thumb";
    const badge = doc.createElement("span");
    badge.className = "kind";
    badge.textContent =
        contentLabels[item.content_type ?? ""] ?? (isLinkKind(item.kind) ? kindLabels[item.kind] : "Link");
    const fallback = () => {
        thumb.classList.add("thumb-fallback");
        thumb.replaceChildren(doc.createTextNode("◉"), badge);
    };
    const imgUrl = safeUrl(item.thumbnail);
    if (imgUrl?.startsWith("https:")) {
        const img = doc.createElement("img");
        img.src = imgUrl;
        img.alt = "";
        img.loading = "lazy";
        img.referrerPolicy = "no-referrer";
        img.onerror = fallback;
        thumb.append(img, badge);
    }
    else {
        fallback();
    }
    const body = doc.createElement("div");
    body.className = "card-body";
    const meta = doc.createElement("div");
    meta.className = "meta";
    const category = doc.createElement("span");
    category.textContent = isCategory(item.category) ? categoryLabels[item.category] : "Novidade";
    const dot = doc.createElement("span");
    dot.className = "dot";
    dot.textContent = "•";
    const channel = doc.createElement("span");
    channel.textContent = item.channel || "Fonte original";
    meta.append(category, dot, channel);
    if (isFresh(item)) {
        const fresh = doc.createElement("span");
        fresh.className = "fresh";
        fresh.textContent = "Novo";
        meta.append(fresh);
    }
    const title = doc.createElement("h3");
    title.textContent = item.title;
    const state = resolveAvailability(item.availability);
    const availability = doc.createElement("span");
    availability.className = `availability ${state}`;
    availability.textContent = availabilityLabels[state];
    const summary = doc.createElement("p");
    summary.className = "summary";
    summary.textContent = item.summary || "Veja os detalhes na fonte original.";
    const bottom = doc.createElement("div");
    bottom.className = "card-bottom";
    const windowLabel = doc.createElement("span");
    windowLabel.className = "window";
    windowLabel.textContent = `${state === "released" ? "Lançamento" : "Estreia"}: ${releaseWindow(item)}`;
    const url = safeUrl(item.url);
    const link = doc.createElement(url ? "a" : "span");
    link.className = "card-link";
    if (url) {
        const typed = item.content_type === "trailer" || item.content_type === "teaser";
        const action = item.kind === "video" && typed
            ? `Assistir ${(contentLabels[item.content_type ?? ""] ?? "").toLowerCase()}`
            : isLinkKind(item.kind)
                ? linkActions[item.kind]
                : "Abrir fonte";
        link.textContent = `${action} ↗`;
        link.setAttribute("href", url);
        link.setAttribute("target", "_blank");
        link.setAttribute("rel", "noopener noreferrer");
        link.setAttribute("aria-label", `${action}: ${item.title} (nova aba)`);
    }
    else {
        link.textContent = "Link indisponível";
    }
    bottom.append(windowLabel, link);
    body.append(meta, title, availability, summary);
    if (item.summary || item.why_it_matters || item.platforms?.length) {
        const details = doc.createElement("details");
        details.className = "card-details";
        const toggle = doc.createElement("summary");
        toggle.textContent = "Ver detalhes";
        details.append(toggle);
        if (item.summary)
            details.append(detailParagraph("Sobre a obra", item.summary, doc));
        if (item.why_it_matters) {
            details.append(detailParagraph("Por que acompanhar", item.why_it_matters, doc));
        }
        if (Array.isArray(item.platforms) && item.platforms.length) {
            details.append(detailParagraph("Onde assistir ou jogar", item.platforms.join(", "), doc));
        }
        body.append(details);
    }
    body.append(bottom);
    article.append(thumb, body);
    return article;
}
function queryRequired(doc, selector) {
    const element = doc.querySelector(selector);
    if (!element)
        throw new Error(`Elemento ausente: ${selector}`);
    return element;
}
export function createApp(doc, options = {}) {
    const fetchImpl = options.fetchImpl ??
        ((input, init) => globalThis.fetch(input, init));
    const timeoutMs = options.timeoutMs ?? 15000;
    const now = options.now ?? (() => new Date());
    const cards = queryRequired(doc, "#cards");
    const status = queryRequired(doc, "#status");
    const statusText = queryRequired(doc, "#status-text");
    const retry = queryRequired(doc, "#retry");
    const refresh = queryRequired(doc, "#refresh");
    const updatedAt = queryRequired(doc, "#updated-at");
    const count = queryRequired(doc, "#result-count");
    const search = queryRequired(doc, "#search");
    const categorySelect = queryRequired(doc, "#category");
    const availabilitySelect = queryRequired(doc, "#availability");
    const sortSelect = queryRequired(doc, "#sort");
    const resetButton = queryRequired(doc, "#reset-filters");
    const tabs = Array.from(doc.querySelectorAll(".tab"));
    let items = [];
    let selectedKind = "all";
    let isLoading = false;
    let hasLoaded = false;
    let loadError = false;
    function loadState() {
        return { hasLoaded, isLoading, loadError };
    }
    function currentFilters() {
        return {
            kind: selectedKind,
            category: categorySelect.value,
            availability: availabilitySelect.value,
            query: search.value,
        };
    }
    function render() {
        const visible = filterItems(items, currentFilters());
        const ordered = sortSelect.value === "soon" ? sortByNearestPremiere(visible) : visible;
        cards.replaceChildren(...ordered.map((item) => makeCard(item, doc)));
        count.textContent = countLabel(visible.length, items.length, loadState());
        refresh.disabled = isLoading;
        refresh.textContent = isLoading ? "Atualizando…" : "Atualizar";
        retry.hidden = !loadError;
        retry.disabled = isLoading;
        const message = statusMessage(loadState(), {
            visible: visible.length,
            total: items.length,
        });
        status.hidden = message === null;
        if (message !== null)
            statusText.textContent = message;
        for (const tab of tabs) {
            const active = tab.dataset.kind === selectedKind;
            tab.classList.toggle("active", active);
            tab.setAttribute("aria-pressed", String(active));
        }
    }
    async function loadItems() {
        if (isLoading)
            return;
        isLoading = true;
        loadError = false;
        render();
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const response = await fetchImpl("/api/releases", { signal: controller.signal });
            if (!response.ok)
                throw new Error("Falha na API");
            const data = await response.json();
            if (!isReleasesResponse(data))
                throw new Error("Resposta inválida");
            items = data.items;
            hasLoaded = true;
            updatedAt.textContent = `Atualizado às ${new Intl.DateTimeFormat("pt-BR", { timeStyle: "short" }).format(now())}`;
        }
        catch {
            loadError = true;
        }
        finally {
            clearTimeout(timeout);
            isLoading = false;
            render();
        }
    }
    function resetFilters() {
        selectedKind = "all";
        categorySelect.value = "all";
        availabilitySelect.value = "all";
        sortSelect.value = "recent";
        search.value = "";
        render();
    }
    for (const tab of tabs) {
        tab.addEventListener("click", () => {
            selectedKind = isTabKind(tab.dataset.kind) ? tab.dataset.kind : "all";
            render();
        });
    }
    search.addEventListener("input", render);
    categorySelect.addEventListener("change", render);
    availabilitySelect.addEventListener("change", render);
    sortSelect.addEventListener("change", render);
    resetButton.addEventListener("click", resetFilters);
    refresh.addEventListener("click", loadItems);
    retry.addEventListener("click", loadItems);
    return {
        loadItems,
        render,
        resetFilters,
        getState: () => ({ items: [...items], selectedKind, ...loadState() }),
    };
}
if (typeof document !== "undefined" && document.querySelector("#cards") !== null) {
    void createApp(document).loadItems();
}
