import type { SearchMatching } from '../../types/api';

export function MatchGroupHeading({
  matching,
  absoluteIndex,
  firstOnPage,
}: {
  matching?: SearchMatching;
  absoluteIndex: number;
  firstOnPage: boolean;
}) {
  if (matching?.mode !== 'all_terms_then_partial') return null;
  const strictCount = matching.all_terms_count;
  if (strictCount == null) return null;
  const isPartial = absoluteIndex >= strictCount;
  if (!firstOnPage && absoluteIndex !== strictCount) return null;
  return (
    <h2 className="col-span-full border-b border-slate-200 pb-2 pt-2 text-base font-semibold text-slate-700">
      {isPartial ? 'Partial matches' : 'Matches all search terms'}
    </h2>
  );
}
