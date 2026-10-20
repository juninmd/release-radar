import { relativeTime } from "../lib/format";
import type { RunSnapshot } from "../lib/types";

const STAT_LABELS: Record<string, string> = {
  discovered: "Links encontrados",
  reserved: "Novos registrados",
  analyzed: "Analisados",
  posted: "Publicados",
  skipped_existing: "Já vistos antes",
  skipped_not_release: "Sem anúncio",
  skipped_released: "Já lançados",
  skipped_unconfirmed: "Não confirmados",
  failed: "Falhas",
};

interface Props {
  run: RunSnapshot | null;
  onStart: (dryRun: boolean) => void;
}

export function RunPanel({ run, onStart }: Props) {
  const running = run?.running ?? false;
  return (
    <div className="run-panel">
      <div className="settings-actions">
        <button
          type="button"
          className="primary-button"
          disabled={running}
          onClick={() => onStart(false)}
        >
          {running ? "Rodada em andamento…" : "Buscar novidades agora"}
        </button>
        <button
          type="button"
          className="text-button"
          disabled={running}
          onClick={() => onStart(true)}
        >
          Simular (sem publicar)
        </button>
      </div>
      {run?.started_at ? (
        <p className="settings-hint">
          Início {relativeTime(run.started_at)}
          {run.finished_at ? ` · fim ${relativeTime(run.finished_at)}` : ""}
        </p>
      ) : null}
      {run?.error ? <p className="settings-error">{run.error}</p> : null}
      {run?.stats ? (
        <ul className="run-stats">
          {Object.entries(run.stats).map(([key, value]) => (
            <li key={key}>
              <span>{STAT_LABELS[key] ?? key}</span>
              <b>{value}</b>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
