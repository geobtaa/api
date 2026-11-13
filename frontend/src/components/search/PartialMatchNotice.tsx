import type { SearchMatching } from '../../types/api';

export function PartialMatchNotice({
  matching,
  totalCount,
}: {
  matching?: SearchMatching;
  totalCount: number;
}) {
  if (!matching?.broadened || totalCount === 0) return null;
  return (
    <p
      role="status"
      className="mb-4 rounded-lg bg-blue-50 p-4 text-sm text-blue-700"
    >
      {matching.mode === 'all_terms_then_partial'
        ? 'Results matching all search terms appear first, followed by partial matches.'
        : 'No results matched all search terms. Showing partial matches.'}
    </p>
  );
}
