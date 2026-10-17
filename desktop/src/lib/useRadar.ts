import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { EMPTY_FILTERS, filterReleases, type Filters } from "./filters";
import { detectNew, mergeSeen } from "./newItems";
import { applySkin } from "./theme";
import type { AppConfig, Release, RunSnapshot } from "./types";

const SEEN_KEY = "radar.seen";

function loadSeen(): string[] {
  try {
    const raw = localStorage.getItem(SEEN_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function saveSeen(ids: string[]): void {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(ids));
  } catch {
    /* armazenamento indisponível: as novidades voltam na próxima abertura */
  }
}

export interface Radar {
  config: AppConfig | null;
  items: Release[];
  visible: Release[];
  filters: Filters;
  setFilters: (filters: Filters) => void;
  loading: boolean;
  error: string | null;
  hasLoaded: boolean;
  lastUpdated: Date | null;
  fresh: Release[];
  run: RunSnapshot | null;
  refresh: () => Promise<void>;
  startRun: (dryRun: boolean) => Promise<void>;
  saveConfig: (next: AppConfig, apiToken?: string) => Promise<void>;
  dismissFresh: () => void;
}

export function useRadar(): Radar {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [items, setItems] = useState<Release[]>([]);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [fresh, setFresh] = useState<Release[]>([]);
  const [run, setRun] = useState<RunSnapshot | null>(null);
  const seenRef = useRef<string[]>(loadSeen());
  const busyRef = useRef(false);

  const refresh = useCallback(async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const next = await api.listReleases();
      const isFirstLoad = seenRef.current.length === 0;
      const novidades = isFirstLoad ? [] : detectNew(seenRef.current, next);
      seenRef.current = mergeSeen(seenRef.current, next);
      saveSeen(seenRef.current);
      setItems(next);
      setLastUpdated(new Date());
      setHasLoaded(true);
      if (novidades.length > 0) {
        setFresh(novidades);
        const label = novidades.length === 1 ? "novidade" : "novidades";
        void api.notify("Release Radar", `${novidades.length} ${label} no radar`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar as novidades.");
    } finally {
      busyRef.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void api.readConfig().then((cfg) => {
      if (cancelled) return;
      setConfig(cfg);
      applySkin(cfg.skin);
      void api.setAlwaysOnTop(cfg.alwaysOnTop);
      // Mostra a janela só quando o webview já vive: no Windows o show() do Rust
      // durante a criação da janela oculta não tem efeito.
      void api.showWindow();
      void refresh();
    });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  const pollMinutes = config?.pollMinutes ?? 0;
  useEffect(() => {
    if (pollMinutes <= 0) return;
    const timer = window.setInterval(() => void refresh(), pollMinutes * 60_000);
    return () => window.clearInterval(timer);
  }, [pollMinutes, refresh]);

  useEffect(() => {
    if (config) applySkin(config.skin);
  }, [config]);

  const startRun = useCallback(
    async (dryRun: boolean) => {
      try {
        const started = await api.startRun(dryRun);
        setRun(started);
        for (;;) {
          await new Promise((resolve) => window.setTimeout(resolve, 2000));
          const snapshot = await api.runStatus();
          setRun(snapshot);
          if (!snapshot.running) break;
        }
        await refresh();
      } catch (err) {
        setRun({
          running: false,
          dry_run: dryRun,
          limit: null,
          started_at: null,
          finished_at: null,
          stats: null,
          error: err instanceof Error ? err.message : "Falha ao iniciar a rodada.",
        });
      }
    },
    [refresh],
  );

  const saveConfig = useCallback(async (next: AppConfig, apiToken?: string) => {
    const saved = await api.saveConfig(next, apiToken);
    setConfig(saved);
    applySkin(saved.skin);
    void api.setAlwaysOnTop(saved.alwaysOnTop);
    return;
  }, []);

  const dismissFresh = useCallback(() => setFresh([]), []);

  const visible = useMemo(() => filterReleases(items, filters), [items, filters]);

  return {
    config,
    items,
    visible,
    filters,
    setFilters,
    loading,
    error,
    hasLoaded,
    lastUpdated,
    fresh,
    run,
    refresh,
    startRun,
    saveConfig,
    dismissFresh,
  };
}
