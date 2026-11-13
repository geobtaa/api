import type { SearchMatching } from '../../types/api';

export function PartialMatchNotice({
  matching,
  totalCount,
}: {
  matching?: SearchMatching;
  totalCount: number;
}) {
  if (
    matching?.mode !== 'partial_terms' ||
    !matching.broadened ||
    totalCount === 0
  )
    return null;
  return (
    <p
      role="status"
      className="mb-4 rounded-lg bg-blue-50 p-4 text-sm text-blue-700"
    >
      No results matched all search terms. Showing partial matches.
    </p>
  );
}
