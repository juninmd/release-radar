const cards = document.querySelector("#cards");
const status = document.querySelector("#status");
const statusText = document.querySelector("#status-text");
const retry = document.querySelector("#retry");
const refresh = document.querySelector("#refresh");
const updatedAt = document.querySelector("#updated-at");
const count = document.querySelector("#result-count");
const search = document.querySelector("#search");
const categorySelect = document.querySelector("#category");
const availabilitySelect = document.querySelector("#availability");
const tabs = [...document.querySelectorAll(".tab")];
let items = [];
let selectedKind = "all";
let isLoading = false;
let hasLoaded = false;
let loadError = false;
const labels = {
  video: "YouTube",
  article: "Artigo",
  catalog: "Página oficial",
};
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

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR");
}

function releaseWindow(item) {
  const value = String(item.release_date || item.release_window || "").trim();
  if (!value || /^(desconhecid[oa]|a definir|unknown)$/i.test(value))
    return "Data a confirmar";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const date = new Date(`${value}T12:00:00Z`);
    if (
      !Number.isNaN(date.valueOf()) &&
      date.toISOString().slice(0, 10) === value
    ) {
      return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "medium",
        timeZone: "UTC",
      }).format(date);
    }
  }
  return value;
}

function detailParagraph(title, text) {
  const section = document.createElement("div");
  const heading = document.createElement("h4");
  heading.textContent = title;
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  section.append(heading, paragraph);
  return section;
}

function makeCard(item) {
  const article = document.createElement("article");
  article.className = "card";
  const thumb = document.createElement("div");
  thumb.className = "thumb";
  const badge = document.createElement("span");
  badge.className = "kind";
  badge.textContent = labels[item.kind] || "Link";
  const fallback = () => {
    thumb.classList.add("thumb-fallback");
    thumb.replaceChildren(document.createTextNode("◉"), badge);
  };
  const imgUrl = safeUrl(item.thumbnail);
  if (imgUrl && imgUrl.startsWith("https:")) {
    const img = document.createElement("img");
    img.src = imgUrl;
    img.alt = "";
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer";
    img.onerror = fallback;
    thumb.append(img, badge);
  } else {
    fallback();
  }
  const body = document.createElement("div");
  body.className = "card-body";
  const meta = document.createElement("div");
  meta.className = "meta";
  const category = document.createElement("span");
  category.textContent = categoryLabels[item.category] || "Novidade";
  const dot = document.createElement("span");
  dot.className = "dot";
  dot.textContent = "•";
  const channel = document.createElement("span");
  channel.textContent = item.channel || "Fonte original";
  meta.append(category, dot, channel);
  const title = document.createElement("h3");
  title.textContent = item.title;
  const availability = document.createElement("span");
  const state = Object.hasOwn(availabilityLabels, item.availability)
    ? item.availability
    : "unconfirmed";
  availability.className = `availability ${state}`;
  availability.textContent = availabilityLabels[state];
  const summary = document.createElement("p");
  summary.className = "summary";
  summary.textContent = item.summary || "Veja os detalhes na fonte original.";
  const bottom = document.createElement("div");
  bottom.className = "card-bottom";
  const windowLabel = document.createElement("span");
  windowLabel.className = "window";
  windowLabel.textContent = `${state === "released" ? "Lançamento" : "Estreia"}: ${releaseWindow(item)}`;
  const url = safeUrl(item.url);
  const link = document.createElement(url ? "a" : "span");
  link.className = "card-link";
  if (url) {
    const action =
      { video: "Assistir", article: "Ler artigo", catalog: "Ver página" }[
        item.kind
      ] || "Abrir fonte";
    link.textContent = `${action} ↗`;
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute("aria-label", `${action}: ${item.title} (nova aba)`);
  } else {
    link.textContent = "Link indisponível";
  }
  bottom.append(windowLabel, link);
  body.append(meta, title, availability, summary);
  if (item.summary || item.why_it_matters || item.platforms?.length) {
    const details = document.createElement("details");
    details.className = "card-details";
    const toggle = document.createElement("summary");
    toggle.textContent = "Ver detalhes";
    details.append(toggle);
    if (item.summary)
      details.append(detailParagraph("Sobre a obra", item.summary));
    if (item.why_it_matters)
      details.append(
        detailParagraph("Por que acompanhar", item.why_it_matters),
      );
    if (Array.isArray(item.platforms) && item.platforms.length)
      details.append(
        detailParagraph("Onde assistir ou jogar", item.platforms.join(", ")),
      );
    body.append(details);
  }
  body.append(bottom);
  article.append(thumb, body);
  return article;
}

function render() {
  const query = normalize(search.value.trim());
  const visible = items.filter(
    (item) =>
      (selectedKind === "all" || item.kind === selectedKind) &&
      (categorySelect.value === "all" ||
        item.category === categorySelect.value) &&
      (availabilitySelect.value === "all" ||
        (item.availability || "unconfirmed") === availabilitySelect.value) &&
      normalize(
        `${item.title} ${item.channel} ${categoryLabels[item.category] || item.category}`,
      ).includes(query),
  );
  cards.replaceChildren(...visible.map(makeCard));
  count.textContent = hasLoaded
    ? `${visible.length} de ${items.length} ${items.length === 1 ? "link" : "links"}`
    : isLoading
      ? "Carregando…"
      : "Indisponível";
  refresh.disabled = isLoading;
  refresh.textContent = isLoading ? "Atualizando…" : "Atualizar";
  retry.hidden = !loadError;
  retry.disabled = isLoading;
  status.hidden =
    !loadError && !(isLoading && !hasLoaded) && visible.length > 0;
  if (loadError)
    statusText.textContent =
      "Não foi possível carregar os links. Tente novamente; seus filtros serão mantidos.";
  else if (isLoading && !hasLoaded)
    statusText.textContent = "Buscando novidades…";
  else if (!visible.length)
    statusText.textContent = items.length
      ? "Nada por aqui com esses filtros. Tente outra busca ou use Limpar filtros."
      : "Ainda não há lançamentos publicados. As próximas descobertas aparecerão aqui.";
  tabs.forEach((tab) => {
    const active = tab.dataset.kind === selectedKind;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-pressed", String(active));
  });
}

async function loadItems() {
  if (isLoading) return;
  isLoading = true;
  loadError = false;
  render();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch("/api/releases", {
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("Falha na API");
    const data = await response.json();
    if (!Array.isArray(data.items)) throw new Error("Resposta inválida");
    items = data.items;
    hasLoaded = true;
    updatedAt.textContent = `Atualizado às ${new Intl.DateTimeFormat("pt-BR", { timeStyle: "short" }).format(new Date())}`;
  } catch {
    loadError = true;
  } finally {
    clearTimeout(timeout);
    isLoading = false;
    render();
  }
}

tabs.forEach((tab) =>
  tab.addEventListener("click", () => {
    selectedKind = tab.dataset.kind;
    render();
  }),
);
search.addEventListener("input", render);
categorySelect.addEventListener("change", render);
availabilitySelect.addEventListener("change", render);
document.querySelector("#reset-filters").addEventListener("click", () => {
  selectedKind = "all";
  categorySelect.value = "all";
  availabilitySelect.value = "all";
  search.value = "";
  render();
});
refresh.addEventListener("click", loadItems);
retry.addEventListener("click", loadItems);
loadItems();
