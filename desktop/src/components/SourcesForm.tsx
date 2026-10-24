import { useEffect, useState } from "react";
import { api } from "../lib/api";

type FieldValue = string | number | boolean;

const TEXT = [
  { key: "youtube_sources", label: "Canais do YouTube", hint: "categoria|@canal, …" },
  { key: "rss_sources", label: "Feeds RSS", hint: "categoria|url, …" },
  { key: "steam_country", label: "País da Steam", hint: "br" },
  { key: "steam_language", label: "Idioma da Steam", hint: "portuguese" },
] as const;

const NUMBERS = [
  { key: "source_limit", label: "Limite por canal" },
  { key: "rss_limit", label: "Limite por feed" },
  { key: "max_items_per_run", label: "Máximo por rodada" },
  { key: "max_transcription_seconds", label: "Duração máxima do vídeo (s)" },
  { key: "steam_limit", label: "Jogos da Steam" },
  { key: "kitsu_limit", label: "Animes do Kitsu" },
  { key: "anilist_limit", label: "Animes do AniList" },
  { key: "jikan_limit", label: "Animes do MyAnimeList" },
  { key: "tvmaze_limit", label: "Séries do TVmaze" },
  { key: "tvmaze_days", label: "Dias à frente (TVmaze)" },
] as const;

const TOGGLES = [
  { key: "analyze_video_content", label: "Transcrever trailers" },
  { key: "steam_enabled", label: "Fonte Steam" },
  { key: "kitsu_enabled", label: "Fonte Kitsu" },
  { key: "anilist_enabled", label: "Fonte AniList" },
  { key: "jikan_enabled", label: "Fonte MyAnimeList (Jikan)" },
  { key: "tvmaze_enabled", label: "Fonte TVmaze" },
] as const;

export function SourcesForm() {
  const [values, setValues] = useState<Record<string, FieldValue> | null>(null);
  const [initial, setInitial] = useState<Record<string, FieldValue> | null>(null);
  const [saved, setSaved] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api
      .readSettings()
      .then((payload) => {
        setValues(payload.values);
        setInitial(payload.values);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const set = (key: string, value: FieldValue) =>
    setValues((current) => (current ? { ...current, [key]: value } : current));

  async function save() {
    if (!values) return;
    // Envia só o que mudou: o resto continua vindo do .env.
    const changed = Object.fromEntries(
      Object.entries(values).filter(([key, value]) => initial?.[key] !== value),
    );
    if (Object.keys(changed).length === 0) {
      setMessage("Nada para salvar: os valores já são os atuais.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const payload = await api.writeSettings(changed);
      setValues(payload.values);
      setInitial(payload.values);
      setSaved(payload.overridden);
      setMessage("Ajustes salvos. A próxima rodada já usa estes valores.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar os ajustes.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !values) return <p className="settings-error">{error}</p>;
  if (!values) return <p className="settings-hint">Carregando fontes e limites…</p>;

  return (
    <div className="sources">
      {TEXT.map((field) => (
        <label key={field.key} className="field">
          <span>{field.label}</span>
          <textarea
            rows={field.key.endsWith("sources") ? 3 : 1}
            placeholder={field.hint}
            value={String(values[field.key] ?? "")}
            onChange={(event) => set(field.key, event.target.value)}
          />
        </label>
      ))}
      <div className="field-grid">
        {NUMBERS.map((field) => (
          <label key={field.key} className="field">
            <span>{field.label}</span>
            <input
              type="number"
              min={0}
              value={Number(values[field.key] ?? 0)}
              onChange={(event) => set(field.key, Number(event.target.value))}
            />
          </label>
        ))}
      </div>
      <div className="field-grid">
        {TOGGLES.map((field) => (
          <label key={field.key} className="toggle">
            <input
              type="checkbox"
              checked={Boolean(values[field.key])}
              onChange={(event) => set(field.key, event.target.checked)}
            />
            <span>{field.label}</span>
          </label>
        ))}
      </div>
      <div className="settings-actions">
        <button type="button" className="primary-button" onClick={() => void save()} disabled={busy}>
          {busy ? "Salvando…" : "Salvar fontes e limites"}
        </button>
        {saved.length > 0 ? <span className="settings-hint">Sobrescritos: {saved.join(", ")}</span> : null}
      </div>
      {message ? <p className="settings-ok">{message}</p> : null}
      {error ? <p className="settings-error">{error}</p> : null}
    </div>
  );
}
