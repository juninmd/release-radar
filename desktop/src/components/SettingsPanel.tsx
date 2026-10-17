import { useState } from "react";
import { api } from "../lib/api";
import { normalizeShortcut, prettyShortcut } from "../lib/format";
import type { AppConfig, RunSnapshot, Skin } from "../lib/types";
import { RunPanel } from "./RunPanel";
import { SourcesForm } from "./SourcesForm";
import { UpdatePanel } from "./UpdatePanel";

const SKINS: { value: Skin; label: string }[] = [
  { value: "dark", label: "Radar (escuro)" },
  { value: "light", label: "Claro" },
  { value: "system", label: "Seguir o sistema" },
];

interface Props {
  config: AppConfig;
  run: RunSnapshot | null;
  onClose: () => void;
  onSaveConfig: (config: AppConfig, token?: string) => Promise<void>;
  onStartRun: (dryRun: boolean) => void;
}

export function SettingsPanel({ config, run, onClose, onSaveConfig, onStartRun }: Props) {
  const [tab, setTab] = useState<"conexao" | "fontes">("conexao");
  const [draft, setDraft] = useState<AppConfig>(config);
  const [token, setToken] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const update = (patch: Partial<AppConfig>) => setDraft({ ...draft, ...patch });

  async function save() {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const next = { ...draft, hasToken: draft.hasToken || Boolean(token) };
      await onSaveConfig(next, token || undefined);
      setToken("");
      setStatus("Ajustes salvos.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar os ajustes.");
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const health = await api.health();
      setStatus(health.status === "ok" ? "Conexão estabelecida com o radar." : `API respondeu: ${health.status}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível alcançar a API.");
    } finally {
      setBusy(false);
    }
  }

  async function removeToken() {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      await onSaveConfig({ ...draft, hasToken: false }, "");
      setToken("");
      setStatus("Token removido.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao remover o token.");
    } finally {
      setBusy(false);
    }
  }

  const insecureBase =
    /^http:\/\//i.test(draft.apiBaseUrl.trim()) &&
    !/^http:\/\/(127\.0\.0\.1|localhost|\[::1\])(:\d+)?/i.test(draft.apiBaseUrl.trim());

  return (
    <section className="overlay" aria-label="Ajustes">
      <header className="overlay-head">
        <h2>Ajustes</h2>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Fechar ajustes">
          ✕
        </button>
      </header>
      <div className="tabs inner" role="group" aria-label="Seção de ajustes">
        <button
          type="button"
          className={`tab${tab === "conexao" ? " active" : ""}`}
          onClick={() => setTab("conexao")}
        >
          Conexão e app
        </button>
        <button
          type="button"
          className={`tab${tab === "fontes" ? " active" : ""}`}
          onClick={() => setTab("fontes")}
        >
          Fontes e rodada
        </button>
      </div>
      <div className="overlay-body">
        {tab === "conexao" ? (
          <>
            <label className="field">
              <span>Endereço da API</span>
              <input
                type="url"
                placeholder="https://radar.exemplo.com"
                value={draft.apiBaseUrl}
                onChange={(event) => update({ apiBaseUrl: event.target.value })}
              />
            </label>
            <label className="field">
              <span>Token de acesso {draft.hasToken ? "(guardado)" : "(opcional)"}</span>
              <input
                type="password"
                placeholder={draft.hasToken ? "••••••••" : "Bearer token da API"}
                value={token}
                onChange={(event) => setToken(event.target.value)}
              />
            </label>
            {draft.hasToken ? (
              <div className="settings-actions">
                <button type="button" className="text-button" onClick={() => void removeToken()} disabled={busy}>
                  Remover token guardado
                </button>
              </div>
            ) : null}
            {insecureBase ? (
              <p className="settings-warn">
                Endereço em http:// fora de localhost: o token viajaria sem TLS até a API.
              </p>
            ) : null}
            <label className="field">
              <span>Buscar novidades a cada (min)</span>
              <input
                type="number"
                min={0}
                value={draft.pollMinutes}
                onChange={(event) => update({ pollMinutes: Number(event.target.value) })}
              />
            </label>
            <label className="field">
              <span>Atalho global para mostrar/ocultar</span>
              <input
                type="text"
                spellCheck={false}
                placeholder="ctrl+shift+r"
                value={draft.shortcut}
                onChange={(event) => update({ shortcut: event.target.value })}
              />
            </label>
            <p className="settings-hint">
              {config.activeShortcut
                ? `Ativo agora: ${prettyShortcut(config.activeShortcut)}`
                : "Nenhum atalho global registrado."}
              {config.activeShortcut &&
              normalizeShortcut(draft.shortcut) !== config.activeShortcut
                ? " — a tecla pedida estava ocupada, usei a primeira livre. Salve para tentar de novo."
                : ""}
            </p>
            <label className="field">
              <span>Aparência</span>
              <select value={draft.skin} onChange={(event) => update({ skin: event.target.value as Skin })}>
                {SKINS.map((skin) => (
                  <option key={skin.value} value={skin.value}>
                    {skin.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="field-grid">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={draft.notify}
                  onChange={(event) => update({ notify: event.target.checked })}
                />
                <span>Notificações do sistema</span>
              </label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={draft.alwaysOnTop}
                  onChange={(event) => update({ alwaysOnTop: event.target.checked })}
                />
                <span>Sempre no topo</span>
              </label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={draft.autostart}
                  onChange={(event) => update({ autostart: event.target.checked })}
                />
                <span>Iniciar com o sistema</span>
              </label>
            </div>
            <div className="settings-actions">
              <button type="button" className="primary-button" onClick={() => void save()} disabled={busy}>
                {busy ? "Salvando…" : "Salvar"}
              </button>
              <button type="button" className="text-button" onClick={() => void testConnection()} disabled={busy}>
                Testar conexão
              </button>
            </div>
            {status ? <p className="settings-ok">{status}</p> : null}
            {error ? <p className="settings-error">{error}</p> : null}
            <h3 className="section-title">Atualizações</h3>
            <UpdatePanel />
          </>
        ) : (
          <>
            <h3 className="section-title">Rodada do bot</h3>
            <RunPanel run={run} onStart={onStartRun} />
            <h3 className="section-title">Fontes e limites</h3>
            <SourcesForm />
          </>
        )}
      </div>
    </section>
  );
}
