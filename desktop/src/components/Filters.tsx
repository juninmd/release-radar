import { AVAILABILITY_OPTIONS, CATEGORY_OPTIONS } from "../lib/format";
import type { Filters as FiltersState } from "../lib/filters";
import type { Release } from "../lib/types";

const TABS: { kind: "all" | Release["kind"]; label: string }[] = [
  { kind: "all", label: "Todos" },
  { kind: "video", label: "▶ YouTube" },
  { kind: "article", label: "↗ Artigos" },
  { kind: "catalog", label: "▣ Páginas oficiais" },
];

interface Props {
  filters: FiltersState;
  onChange: (filters: FiltersState) => void;
}

export function Filters({ filters, onChange }: Props) {
  const update = (patch: Partial<FiltersState>) => onChange({ ...filters, ...patch });
  return (
    <div className="filters">
      <div className="tabs" role="group" aria-label="Tipo de link">
        {TABS.map((tab) => (
          <button
            key={tab.kind}
            type="button"
            className={`tab${filters.kind === tab.kind ? " active" : ""}`}
            aria-pressed={filters.kind === tab.kind}
            onClick={() => update({ kind: tab.kind })}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <label className="search">
        <svg className="search-icon" viewBox="0 0 20 20" aria-hidden="true">
          <circle cx="9" cy="9" r="6" />
          <path d="M13.6 13.6 18 18" />
        </svg>
        <span className="sr-only">Buscar lançamento</span>
        <input
          type="search"
          placeholder="Buscar título ou fonte…"
          autoComplete="off"
          value={filters.query}
          onChange={(event) => update({ query: event.target.value })}
        />
      </label>
      <div className="filter-row">
        <label className="select">
          Categoria
          <select value={filters.category} onChange={(event) => update({ category: event.target.value })}>
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="select">
          Disponibilidade
          <select
            value={filters.availability}
            onChange={(event) =>
              update({ availability: event.target.value as FiltersState["availability"] })
            }
          >
            {AVAILABILITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="text-button"
          onClick={() => onChange({ kind: "all", category: "all", availability: "all", query: "" })}
        >
          Limpar filtros
        </button>
      </div>
    </div>
  );
}
