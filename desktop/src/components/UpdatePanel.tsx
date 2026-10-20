import { useEffect, useState } from "react";
import { isTauri } from "../lib/api";
import { checkForUpdate, currentVersion, installUpdate, type UpdateInfo } from "../lib/updater";

export function UpdatePanel() {
  const [version, setVersion] = useState<string | null>(null);
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void currentVersion().then(setVersion);
  }, []);

  async function check() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await checkForUpdate();
      setInfo(result);
      setMessage(
        result.available
          ? `Versão ${result.version} disponível para instalar.`
          : "Você já está na última versão publicada.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível verificar atualizações.");
    } finally {
      setBusy(false);
    }
  }

  async function install() {
    setBusy(true);
    setError(null);
    try {
      await installUpdate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao instalar a atualização.");
      setBusy(false);
    }
  }

  if (!isTauri()) {
    return <p className="settings-hint">Atualizações ficam disponíveis no app instalado.</p>;
  }

  return (
    <div className="update-panel">
      <p className="settings-hint">Versão instalada: {version ?? "…"}</p>
      <div className="settings-actions">
        <button type="button" className="text-button" onClick={() => void check()} disabled={busy}>
          {busy ? "Verificando…" : "Verificar atualizações"}
        </button>
        {info?.available ? (
          <button type="button" className="primary-button" onClick={() => void install()} disabled={busy}>
            Atualizar e reiniciar
          </button>
        ) : null}
      </div>
      {message ? <p className="settings-ok">{message}</p> : null}
      {error ? <p className="settings-error">{error}</p> : null}
    </div>
  );
}
