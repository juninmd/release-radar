import type { Availability, Kind } from "./types";

export const KIND_LABELS: Record<Kind, string> = {
  video: "YouTube",
  article: "Artigo",
  catalog: "Página oficial",
};

export const KIND_ACTIONS: Record<Kind, string> = {
  video: "Assistir",
  article: "Ler artigo",
  catalog: "Ver página",
};

export const CATEGORY_LABELS: Record<string, string> = {
  movies: "Filmes",
  series: "Séries",
  games: "Jogos",
  anime: "Animes",
};

export const AVAILABILITY_LABELS: Record<Availability, string> = {
  upcoming: "Vai estrear",
  released: "Já disponível",
  unconfirmed: "A confirmar",
};

export const CATEGORY_OPTIONS = [
  { value: "all", label: "Todas" },
  { value: "movies", label: "Filmes" },
  { value: "series", label: "Séries" },
  { value: "games", label: "Jogos" },
  { value: "anime", label: "Animes" },
];

export const AVAILABILITY_OPTIONS = [
  { value: "all", label: "Todas" },
  { value: "upcoming", label: "Vai estrear" },
  { value: "released", label: "Já disponível" },
  { value: "unconfirmed", label: "A confirmar" },
];

/** Compara texto sem acentos e sem caixa, como o painel web. */
export function normalize(value: unknown): string {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR");
}

/** Só devolve URLs http(s) sem credenciais embutidas. */
export function safeUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    if (url.username || url.password) return null;
    return url.href;
  } catch {
    return null;
  }
}

function isoDate(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T12:00:00Z`);
  return date.toISOString().slice(0, 10) === value ? date : null;
}

/** Data legível da estreia, caindo para a janela textual quando não há ISO. */
export function releaseWindow(item: {
  release_date?: string;
  release_window?: string;
}): string {
  const value = String(item.release_date || item.release_window || "").trim();
  if (!value || /^(desconhecid[oa]|a definir|unknown)$/i.test(value)) return "Data a confirmar";
  const date = isoDate(value);
  if (date) {
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeZone: "UTC" }).format(date);
  }
  return value;
}

export function shortTime(value: string | number | Date | null | undefined): string {
  if (!value) return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.valueOf())) return "";
  return new Intl.DateTimeFormat("pt-BR", { timeStyle: "short" }).format(date);
}

export function relativeTime(value: string | number | Date | null | undefined): string {
  if (!value) return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.valueOf())) return "";
  const diff = Date.now() - date.valueOf();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "agora";
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `há ${hours} h`;
  const days = Math.floor(hours / 24);
  return `há ${days} d`;
}

const KEY_NAMES: Record<string, string> = {
  ctrl: "Ctrl",
  control: "Ctrl",
  alt: "Alt",
  shift: "Shift",
  super: "Super",
  cmd: "Cmd",
  space: "Space",
  enter: "Enter",
  tab: "Tab",
  escape: "Esc",
};

/** "ctrl+shift+r" -> "Ctrl+Shift+R" (mesma regra do Rust). */
export function prettyShortcut(value: string | null | undefined): string {
  if (!value) return "";
  return String(value)
    .toLowerCase()
    .split("+")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => KEY_NAMES[part] ?? part.toUpperCase())
    .join("+");
}

export function normalizeShortcut(value: string): string {
  return String(value)
    .toLowerCase()
    .split("+")
    .map((part) => part.trim())
    .filter(Boolean)
    .join("+");
}
