export function JobLibrarySkeleton() {
  return (
    <div className="library-skeleton" role="status" aria-label="Loading saved opportunities">
      {[0, 1, 2].map((item) => (
        <div className="library-skeleton-row" key={item}>
          <span className="skeleton-block wide" />
          <span className="skeleton-block pill" />
          <span className="skeleton-block text" />
        </div>
      ))}
    </div>
  );
}
