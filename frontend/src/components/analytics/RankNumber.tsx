export function RankNumber({
  rank,
  className = '',
}: {
  rank: number;
  className?: string;
}) {
  return (
    <span
      className={`analytics-rank-number${rank === 1 ? ' analytics-rank-number--leader' : ''} ${className}`.trim()}
      aria-label={`Rank ${rank}`}
    >
      <span aria-hidden="true">#</span>
      {rank}
    </span>
  );
}
