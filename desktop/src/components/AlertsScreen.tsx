import { api } from "../lib/api";
import { KIND_ACTIONS, KIND_LABELS, relativeTime, safeUrl } from "../lib/format";
import type { Release } from "../lib/types";

interface Props {
  items: Release[];
  onDismiss: () => void;
  onClose: () => void;
}

export function AlertsScreen({ items, onDismiss, onClose }: Props) {
  return (
    <section className="overlay" aria-label="Novidades">
      <header className="overlay-head">
        <h2>Novidades no radar</h2>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Fechar novidades">
          ✕
        </button>
      </header>
      <div className="overlay-body">
        {items.length === 0 ? (
          <p className="settings-hint">Nenhuma novidade desde a última verificação.</p>
        ) : (
          <ul className="alert-list">
            {items.map((item) => {
              const url = safeUrl(item.url);
              return (
                <li key={item.id} className="alert-card">
                  <span className="kind">{KIND_LABELS[item.kind] ?? "Link"}</span>
                  <h3>{item.title}</h3>
                  <p className="alert-meta">
                    {item.channel || "Fonte original"} · {relativeTime(item.posted_at)}
                  </p>
                  {url ? (
                    <button type="button" className="card-link" onClick={() => void api.openLink(url)}>
                      {KIND_ACTIONS[item.kind] ?? "Abrir fonte"} ↗
                    </button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
        <div className="settings-actions">
          <button type="button" className="text-button" onClick={onDismiss}>
            Marcar como visto
          </button>
        </div>
      </div>
    </section>
  );
}
