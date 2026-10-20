import { useState } from "react";
import { api } from "../lib/api";
import {
  AVAILABILITY_LABELS,
  CATEGORY_LABELS,
  KIND_ACTIONS,
  KIND_LABELS,
  releaseWindow,
  safeUrl,
} from "../lib/format";
import type { Availability, Release } from "../lib/types";

function Detail({ title, text }: { title: string; text: string }) {
  return (
    <div className="detail">
      <h4>{title}</h4>
      <p>{text}</p>
    </div>
  );
}

export function ReleaseCard({ item }: { item: Release }) {
  const [imageState, setImageState] = useState<"loading" | "ready" | "error">("loading");
  const thumbnail = safeUrl(item.thumbnail);
  const url = safeUrl(item.url);
  const state: Availability =
    item.availability in AVAILABILITY_LABELS ? item.availability : "unconfirmed";
  const action = KIND_ACTIONS[item.kind] ?? "Abrir fonte";
  const hasDetails = Boolean(item.summary || item.why_it_matters || item.platforms.length);
  const showImage = Boolean(thumbnail) && imageState !== "error";

  return (
    <article className="card">
      <div className={`thumb${showImage ? "" : " thumb-fallback"}`}>
        {showImage ? (
          <>
            <img
              src={thumbnail ?? ""}
              alt=""
              loading="lazy"
              referrerPolicy="no-referrer"
              className={imageState === "loading" ? "is-loading" : ""}
              onLoad={() => setImageState("ready")}
              onError={() => setImageState("error")}
            />
            <span className="thumb-scrim" aria-hidden="true" />
          </>
        ) : (
          <span className="thumb-mark" aria-hidden="true">
            ◉
          </span>
        )}
        <span className="kind">{KIND_LABELS[item.kind] ?? "Link"}</span>
      </div>
      <div className="card-body">
        <div className="meta">
          <span className="category">{CATEGORY_LABELS[item.category] ?? "Novidade"}</span>
          <span className="meta-sep" aria-hidden="true">
            ·
          </span>
          <span className="channel">{item.channel || "Fonte original"}</span>
        </div>
        <h3>{item.title}</h3>
        <span className={`availability ${state}`}>
          <i aria-hidden="true" />
          {AVAILABILITY_LABELS[state]}
        </span>
        <p className="summary">{item.summary || "Veja os detalhes na fonte original."}</p>
        {hasDetails ? (
          <details className="card-details">
            <summary>Ver detalhes</summary>
            {item.summary ? <Detail title="Sobre a obra" text={item.summary} /> : null}
            {item.why_it_matters ? (
              <Detail title="Por que acompanhar" text={item.why_it_matters} />
            ) : null}
            {item.platforms.length > 0 ? (
              <Detail title="Onde assistir ou jogar" text={item.platforms.join(", ")} />
            ) : null}
          </details>
        ) : null}
        <div className="card-bottom">
          <span className="window">
            <span className="window-label">{state === "released" ? "Lançamento" : "Estreia"}</span>
            {releaseWindow(item)}
          </span>
          {url ? (
            <button
              type="button"
              className="card-link"
              onClick={() => void api.openLink(url)}
              aria-label={`${action}: ${item.title}`}
            >
              {action}
              <span aria-hidden="true"> ↗</span>
            </button>
          ) : (
            <span className="card-link disabled">Link indisponível</span>
          )}
        </div>
      </div>
    </article>
  );
}
