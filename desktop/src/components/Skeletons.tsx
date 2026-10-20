/** Cartão de esqueleto enquanto a primeira carga não chega. */
export function CardSkeleton() {
  return (
    <article className="card skeleton" aria-hidden="true">
      <div className="thumb" />
      <div className="card-body">
        <span className="sk sk-meta" />
        <span className="sk sk-title" />
        <span className="sk sk-pill" />
        <span className="sk sk-line" />
        <span className="sk sk-line short" />
      </div>
    </article>
  );
}

export function CardSkeletonList({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <CardSkeleton key={index} />
      ))}
    </>
  );
}
