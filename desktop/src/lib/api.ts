import { invoke } from "@tauri-apps/api/core";
import type {
  AppConfig,
  Health,
  Release,
  RunSnapshot,
  SettingsPayload,
} from "./types";

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function browserToken(): string {
  try {
    return localStorage.getItem("radar.apiToken") ?? "";
  } catch {
    return "";
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const token = browserToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    let message = `Falha na API (${response.status})`;
    try {
      const payload = (await response.json()) as { error?: string };
      if (payload.error) message = payload.error;
    } catch {
      /* corpo sem JSON: mantém a mensagem padrão */
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

/**
 * Fora do Tauri (navegador) as chamadas passam pelo proxy `/api` do Vite, então
 * leitura e escrita funcionam em desenvolvimento; só o token guardado no Rust e
 * as funções do sistema (bandeja, atalho, update) existem apenas no app.
 */
export const api = {
  health(): Promise<Health> {
    return isTauri() ? invoke<Health>("health") : http<Health>("/api/health");
  },
  listReleases(): Promise<Release[]> {
    return isTauri()
      ? invoke<Release[]>("list_releases")
      : http<{ items: Release[] }>("/api/releases").then((data) => data.items);
  },
  readSettings(): Promise<SettingsPayload> {
    return isTauri()
      ? invoke<SettingsPayload>("read_settings")
      : http<SettingsPayload>("/api/settings");
  },
  async writeSettings(values: Record<string, unknown>): Promise<SettingsPayload> {
    if (isTauri()) return invoke<SettingsPayload>("write_settings", { values });
    return http<SettingsPayload>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(values),
    });
  },
  async startRun(dryRun: boolean): Promise<RunSnapshot> {
    if (isTauri()) return invoke<RunSnapshot>("start_run", { dryRun });
    return http<RunSnapshot>("/api/run", {
      method: "POST",
      body: JSON.stringify({ dry_run: dryRun }),
    });
  },
  runStatus(): Promise<RunSnapshot> {
    return isTauri() ? invoke<RunSnapshot>("run_status") : http<RunSnapshot>("/api/run");
  },
  readConfig(): Promise<AppConfig> {
    return isTauri() ? invoke<AppConfig>("read_config") : Promise.resolve(browserConfig());
  },
  async saveConfig(config: AppConfig, apiToken?: string): Promise<AppConfig> {
    if (isTauri()) {
      return invoke<AppConfig>("save_config", { config, apiToken: apiToken ?? null });
    }
    saveBrowserConfig(config, apiToken);
    return {
      ...config,
      hasToken: apiToken === undefined ? config.hasToken : Boolean(apiToken),
    };
  },
  notify(title: string, body: string): Promise<void> {
    if (!isTauri()) return Promise.resolve();
    return invoke<void>("notify", { title, body });
  },
  openLink(url: string): Promise<void> {
    if (isTauri()) return invoke<void>("open_link", { url });
    window.open(url, "_blank", "noopener,noreferrer");
    return Promise.resolve();
  },
  toggleWindow(): Promise<void> {
    return isTauri() ? invoke<void>("toggle_window") : Promise.resolve();
  },
  showWindow(): Promise<void> {
    return isTauri() ? invoke<void>("show_window") : Promise.resolve();
  },
  hideWindow(): Promise<void> {
    return isTauri() ? invoke<void>("hide_window") : Promise.resolve();
  },
  setAlwaysOnTop(value: boolean): Promise<void> {
    return isTauri() ? invoke<void>("set_always_on_top", { value }) : Promise.resolve();
  },
};

const BROWSER_CONFIG_KEY = "radar.config";

export function browserConfig(): AppConfig {
  const fallback: AppConfig = {
    apiBaseUrl: "",
    pollMinutes: 10,
    notify: true,
    alwaysOnTop: true,
    autostart: false,
    skin: "dark",
    shortcut: "ctrl+shift+r",
    hasToken: false,
    activeShortcut: null,
  };
  try {
    const raw = localStorage.getItem(BROWSER_CONFIG_KEY);
    const merged = raw ? { ...fallback, ...(JSON.parse(raw) as Partial<AppConfig>) } : fallback;
    return { ...merged, hasToken: Boolean(browserToken()) };
  } catch {
    return fallback;
  }
}

function saveBrowserConfig(config: AppConfig, apiToken?: string): void {
  try {
    const { hasToken: _hasToken, activeShortcut: _active, ...rest } = config;
    localStorage.setItem(BROWSER_CONFIG_KEY, JSON.stringify(rest));
    // undefined mantém o token atual; "" (explícito) remove.
    if (apiToken !== undefined) {
      if (apiToken) localStorage.setItem("radar.apiToken", apiToken);
      else localStorage.removeItem("radar.apiToken");
    }
  } catch {
    /* armazenamento indisponível: ignora em modo navegador */
  }
}
