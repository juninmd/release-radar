interface Props {
  title: string;
  hint: string;
}

/** Estado vazio com uma pequena arte de radar (CSS puro). */
export function EmptyState({ title, hint }: Props) {
  return (
    <div className="empty">
      <div className="empty-art" aria-hidden="true">
        <span className="ring r1" />
        <span className="ring r2" />
        <span className="ring r3" />
        <span className="sweep" />
        <span className="core" />
      </div>
      <p className="empty-title">{title}</p>
      <p className="empty-hint">{hint}</p>
    </div>
  );
}
