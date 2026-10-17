import { useEffect, useState } from "react";
import { AlertsScreen } from "./components/AlertsScreen";
import { EmptyState } from "./components/EmptyState";
import { Filters } from "./components/Filters";
import { Header } from "./components/Header";
import { ReleaseCard } from "./components/ReleaseCard";
import { SettingsPanel } from "./components/SettingsPanel";
import { CardSkeletonList } from "./components/Skeletons";
import { StatusBar } from "./components/StatusBar";
import { api, isTauri } from "./lib/api";
import { useRadar } from "./lib/useRadar";

type View = "list" | "settings" | "alerts";

export default function App() {
  const radar = useRadar();
  const [view, setView] = useState<View>("list");

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setView("list");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    // Só abre quando chega um conjunto novo de novidades; fechar (✕/Esc) não reabre.
    if (radar.fresh.length > 0) setView("alerts");
  }, [radar.fresh]);

  useEffect(() => {
    if (!isTauri()) return;
    let cancelled = false;
    const unlisten: Array<() => void> = [];
    void (async () => {
      const { listen } = await import("@tauri-apps/api/event");
      const handles = await Promise.all([
        listen("radar://refresh", () => void radar.refresh()),
        listen("radar://run", () => void radar.startRun(false)),
        listen("radar://settings", () => setView("settings")),
      ]);
      if (cancelled) handles.forEach((unsubscribe) => unsubscribe());
      else unlisten.push(...handles);
    })();
    return () => {
      cancelled = true;
      unlisten.forEach((unsubscribe) => unsubscribe());
    };
  }, [radar.refresh, radar.startRun]);

  const pinned = radar.config?.alwaysOnTop ?? true;
  const togglePin = () => {
    if (!radar.config) return;
    void radar.saveConfig({ ...radar.config, alwaysOnTop: !radar.config.alwaysOnTop });
  };

  return (
    <div className="app">
      <Header
        online={!radar.error}
        freshCount={radar.fresh.length}
        pinned={pinned}
        onBell={() => setView("alerts")}
        onTogglePin={togglePin}
        onHide={() => void api.hideWindow()}
        onSettings={() => setView("settings")}
      />
      <main className="content">
        <Filters filters={radar.filters} onChange={radar.setFilters} />
        <StatusBar
          loading={radar.loading}
          error={radar.error}
          hasLoaded={radar.hasLoaded}
          visibleCount={radar.visible.length}
          totalCount={radar.items.length}
          lastUpdated={radar.lastUpdated}
          onRefresh={() => void radar.refresh()}
        />
        <div className="cards" aria-live="polite">
          {!radar.hasLoaded && radar.loading ? (
            <CardSkeletonList count={3} />
          ) : radar.hasLoaded && radar.items.length === 0 ? (
            <EmptyState
              title="Ainda não há lançamentos"
              hint="As próximas descobertas aparecem aqui assim que o bot publicar."
            />
          ) : (
            radar.visible.map((item) => <ReleaseCard key={item.id} item={item} />)
          )}
        </div>
      </main>
      <footer className="footer">
        <span>RELEASE RADAR</span>
        <span>{radar.items.length} links no radar</span>
      </footer>
      {view === "settings" && radar.config ? (
        <SettingsPanel
          config={radar.config}
          run={radar.run}
          onClose={() => setView("list")}
          onSaveConfig={radar.saveConfig}
          onStartRun={(dryRun) => void radar.startRun(dryRun)}
        />
      ) : null}
      {view === "alerts" ? (
        <AlertsScreen
          items={radar.fresh}
          onDismiss={radar.dismissFresh}
          onClose={() => setView("list")}
        />
      ) : null}
    </div>
  );
}
