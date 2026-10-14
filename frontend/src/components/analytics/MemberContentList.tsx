import { Eye, Download } from 'lucide-react';
import { ResourceThumbnail } from './ResourceThumbnail';
import { useRanking } from './useRanking';
import { RankingRow } from './RankingRow';
import { ReportPanelHeader } from './ReportPanelHeader';
import type { MemberContentEntry } from '../../data/analytics/memberJuly2026';

export function MemberContentList({
  title,
  items,
  metric,
  emptyMessage,
}: {
  title: string;
  items: MemberContentEntry[];
  metric: 'views' | 'downloads';
  emptyMessage: string;
}) {
  const topItems = items.slice(0, metric === 'views' ? 50 : 25);
  const ranking = useRanking(
    topItems,
    (item) => item[metric],
    title,
    metric === 'views' ? 'views' : 'downloads'
  );
  return (
    <section
      className="analytics-panel analytics-panel--ranking analytics-member-leading-table"
      aria-label={title}
    >
      <ReportPanelHeader
        title={title}
        icon={metric === 'views' ? Eye : Download}
      >
        <small>Top {topItems.length}</small>
      </ReportPanelHeader>
      {topItems.length > 0 ? (
        <>
          {ranking.controls}
          <div className="analytics-ranking-list">
            {ranking.visible.map(({ row: item, rank }) => (
              <RankingRow
                key={item.id}
                rank={rank}
                title={item.title}
                href={`/resources/${encodeURIComponent(item.id)}`}
                thumbnail={
                  <ResourceThumbnail resource={item} eager={rank === 1} />
                }
                value={item[metric]}
                label={metric === 'views' ? 'views' : 'download clicks'}
                maximum={Math.max(1, ...topItems.map((row) => row[metric]))}
              />
            ))}
            {!ranking.visible.length && (
              <p className="analytics-member-empty">
                No resources match your search.
              </p>
            )}
          </div>
        </>
      ) : (
        <p className="analytics-member-empty">{emptyMessage}</p>
      )}
    </section>
  );
}
