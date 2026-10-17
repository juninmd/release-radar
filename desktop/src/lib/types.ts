export type Kind = "video" | "article" | "catalog";

export type Availability = "upcoming" | "released" | "unconfirmed";

export type Skin = "dark" | "light" | "system";

export interface Release {
  id: string;
  source: string;
  kind: Kind;
  title: string;
  url: string;
  channel: string | null;
  category: string;
  thumbnail: string | null;
  summary: string;
  release_window: string;
  release_date: string;
  availability: Availability;
  why_it_matters: string;
  platforms: string[];
  posted_at: string | null;
}

export interface SettingsPayload {
  values: Record<string, string | number | boolean>;
  defaults: Record<string, string | number | boolean>;
  overridden: string[];
  saved?: string[];
}

export interface RunStats {
  discovered: number;
  reserved: number;
  analyzed: number;
  posted: number;
  skipped_existing: number;
  skipped_not_release: number;
  skipped_released: number;
  skipped_unconfirmed: number;
  failed: number;
}

export interface RunSnapshot {
  accepted?: boolean;
  running: boolean;
  dry_run: boolean;
  limit: number | null;
  started_at: string | null;
  finished_at: string | null;
  stats: RunStats | null;
  error: string | null;
}

export interface AppConfig {
  apiBaseUrl: string;
  pollMinutes: number;
  notify: boolean;
  alwaysOnTop: boolean;
  autostart: boolean;
  skin: Skin;
  /** Acelerador desejado, ex.: "ctrl+alt+r". */
  shortcut: string;
  /** O token nunca volta para a interface; só indicamos se há um guardado. */
  hasToken: boolean;
  /** Atalho global de fato registrado — pode ser uma alternativa livre. */
  activeShortcut: string | null;
}

export interface Health {
  status: string;
  service: string;
}
