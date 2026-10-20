interface Props {
  online: boolean;
  freshCount: number;
  pinned: boolean;
  onBell: () => void;
  onTogglePin: () => void;
  onHide: () => void;
  onSettings: () => void;
}

export function Header({ online, freshCount, pinned, onBell, onTogglePin, onHide, onSettings }: Props) {
  return (
    <header className="topbar" data-tauri-drag-region>
      <div className="brand" data-tauri-drag-region>
        <span className="brand-mark" aria-hidden="true">
          ◉
        </span>
        <span>
          RELEASE<b>RADAR</b>
        </span>
      </div>
      <div className="topbar-actions">
        <span
          className={`conn ${online ? "online" : "offline"}`}
          title={online ? "API acessível" : "Sem conexão com a API"}
          aria-label={online ? "API acessível" : "Sem conexão com a API"}
        />
        <button
          type="button"
          className={`icon-button bell${freshCount > 0 ? " has-fresh" : ""}`}
          onClick={onBell}
          aria-label={freshCount > 0 ? `${freshCount} novidades` : "Novidades"}
        >
          🔔{freshCount > 0 ? <span className="badge">{freshCount}</span> : null}
        </button>
        <button
          type="button"
          className={`icon-button${pinned ? " active" : ""}`}
          onClick={onTogglePin}
          aria-pressed={pinned}
          aria-label="Sempre no topo"
          title="Sempre no topo"
        >
          📌
        </button>
        <button type="button" className="icon-button" onClick={onSettings} aria-label="Ajustes" title="Ajustes">
          ⚙
        </button>
        <button type="button" className="icon-button" onClick={onHide} aria-label="Ocultar" title="Ocultar (Ctrl+Shift+R)">
          —
        </button>
      </div>
    </header>
  );
}
