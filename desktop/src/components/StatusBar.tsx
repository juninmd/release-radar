import { relativeTime } from "../lib/format";

interface Props {
  loading: boolean;
  error: string | null;
  hasLoaded: boolean;
  visibleCount: number;
  totalCount: number;
  lastUpdated: Date | null;
  onRefresh: () => void;
}

export function StatusBar({
  loading,
  error,
  hasLoaded,
  visibleCount,
  totalCount,
  lastUpdated,
  onRefresh,
}: Props) {
  const noun = totalCount === 1 ? "link" : "links";
  const count = hasLoaded ? `${visibleCount} de ${totalCount} ${noun}` : loading ? "Carregando…" : "Indisponível";
  const message = error
    ? "Não foi possível carregar as novidades. Tente novamente; seus filtros serão mantidos."
    : !hasLoaded && loading
      ? "Buscando novidades…"
      : totalCount > 0 && visibleCount === 0
        ? "Nada por aqui com esses filtros. Tente outra busca ou use Limpar filtros."
        : "";

  return (
    <div className="status-bar">
      <p className="result-count" aria-live="polite">
        {count}
        {lastUpdated ? <span className="updated-at"> · {relativeTime(lastUpdated)}</span> : null}
      </p>
      <div className="status-actions">
        {message ? <span className="status-text">{message}</span> : null}
        {error ? (
          <button type="button" className="refresh-button" onClick={onRefresh} disabled={loading}>
            Tentar novamente
          </button>
        ) : (
          <button
            type="button"
            className="refresh-button ghost"
            onClick={onRefresh}
            disabled={loading}
          >
            <span className={`refresh-glyph${loading ? " spinning" : ""}`} aria-hidden="true">
              ↻
            </span>
            {loading ? "Atualizando" : "Atualizar"}
          </button>
        )}
      </div>
    </div>
  );
}
