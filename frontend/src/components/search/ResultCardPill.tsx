import React from 'react';

export interface ResultCardPillProps {
  /** Index year - only shown when definitive (truthy number) */
  indexYear?: number | null;
  /** Resource class (e.g. "Datasets", "Maps") */
  resourceClass?: string | null;
  /** Provider institution name (reserved for future icon use) */
  provider?: string | null;
  className?: string;
}

/**
 * Pill for search result cards: Year · Resource Class.
 * Omits Index Year when not definitive (avoids "— · Datasets").
 */
export function ResultCardPill({
  indexYear,
  resourceClass,
  className,
}: ResultCardPillProps) {
  const hasDefinitiveYear =
    indexYear != null &&
    typeof indexYear === 'number' &&
    !Number.isNaN(indexYear);
  const displayResourceClass = resourceClass || 'Item';

  const textContent = hasDefinitiveYear ? (
    <>
      <span>{indexYear}</span>
      <span className="mx-1.5 opacity-90" aria-hidden>
        ·
      </span>
      <span>{displayResourceClass}</span>
    </>
  ) : (
    <span>{displayResourceClass}</span>
  );

  const basePillClass =
    'inline-flex items-center rounded text-xs uppercase tracking-tighter text-white bg-[#003c5b] px-1.5 py-0.5';

  return (
    <span
      className={[basePillClass, className].filter(Boolean).join(' ')}
      data-testid="result-card-pill"
    >
      {textContent}
    </span>
  );
}
