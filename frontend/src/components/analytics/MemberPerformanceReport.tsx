import { useState } from 'react';
import { Link } from 'react-router';
import { Trophy } from 'lucide-react';
import type { MemberPerformanceEntry } from '../../data/analytics/july2026';
import { BTAA_PARTNER_INSTITUTIONS } from '../../constants/partnerInstitutions';
import { RankingRow } from './RankingRow';
import { ReportPanelHeader } from './ReportPanelHeader';

const number = new Intl.NumberFormat('en-US');
const metrics = {
  resourceViews: 'Views',
  downloadClicks: 'Download clicks',
  impressions: 'Search appearances',
  activeResources: 'Resources with activity',
  catalogRecords: 'Published resources',
  sourceClicks: 'Source-site clicks',
};
type Metric = keyof typeof metrics;

export function MemberPerformanceReport({
  members,
}: {
  members: MemberPerformanceEntry[];
}) {
  const [filter, setFilter] = useState('');
  const [sort, setSort] = useState<Metric | 'name'>('resourceViews');
  const metric = sort === 'name' ? 'resourceViews' : sort;
  const ranked = [...members].sort((a, b) => b[metric] - a[metric]);
  const terms = filter.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const rows = [
    ...ranked.map((member, index) => ({
      member,
      rank: index + 1,
      name: member.name,
      institution: BTAA_PARTNER_INSTITUTIONS.find(
        (entry) => entry.slug === member.slug
      ),
    })),
    ...BTAA_PARTNER_INSTITUTIONS.filter(
      (institution) =>
        !members.some((member) => member.slug === institution.slug)
    ).map((institution) => ({
      member: undefined,
      rank: undefined,
      name: institution.name,
      institution,
    })),
  ];
  const visible = rows
    .filter(({ member, name, institution }) =>
      terms.every((term) =>
        `${name} ${member?.shortName ?? ''} ${institution?.slug === 'university-of-southern-california' ? 'USC' : ''} ${member?.topResource.title ?? ''}`
          .toLowerCase()
          .includes(term)
      )
    )
    .sort((a, b) =>
      sort === 'name'
        ? a.name.localeCompare(b.name)
        : (a.rank ?? Infinity) - (b.rank ?? Infinity)
    );
  return (
    <section
      className="analytics-panel analytics-panel--ranking analytics-member-report"
      aria-label="Activity by member institution"
    >
      <ReportPanelHeader title="Activity by member institution" icon={Trophy}>
        <small>
          {rows.length} institutions · {members.length} with recorded data
        </small>
      </ReportPanelHeader>
      <div className="analytics-table-tools analytics-table-tools--inset">
        <label>
          Filter institutions
          <input
            type="search"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Search institutions or content…"
          />
        </label>
        <label>
          Sort by
          <select
            aria-label="Sort member performance"
            value={sort}
            onChange={(event) => setSort(event.target.value as Metric | 'name')}
          >
            {Object.entries(metrics).map(([key, label]) => (
              <option value={key} key={key}>
                Most {label.toLowerCase()}
              </option>
            ))}
            <option value="name">Institution A–Z</option>
          </select>
        </label>
        <span role="status">
          {visible.length} of {rows.length} institutions
        </span>
      </div>
      <div className="analytics-ranking-list">
        {visible.map(({ member, rank, name, institution }) =>
          member ? (
            <RankingRow
              key={member.code}
              rank={rank!}
              title={member.name}
              href={`/search?${new URLSearchParams({ 'include_filters[b1g_code_s][]': member.code })}`}
              thumbnail={
                <span className="analytics-member-logo">
                  <img
                    src={`/icons/${member.iconSlug}.svg`}
                    alt=""
                    loading="lazy"
                  />
                </span>
              }
              value={member[metric]}
              label={metrics[metric].toLowerCase()}
              maximum={Math.max(1, ...members.map((row) => row[metric]))}
            >
              <dl className="analytics-member-row-details">
                {Object.entries(metrics)
                  .filter(([key]) => key !== metric)
                  .map(([key, label]) => (
                    <div key={key}>
                      <dt>{label}</dt>
                      <dd>{number.format(member[key as Metric])}</dd>
                    </div>
                  ))}
              </dl>
              {member.topResource.id && (
                <p className="analytics-member-row-content">
                  Top-viewed content:{' '}
                  <Link
                    to={`/resources/${encodeURIComponent(member.topResource.id)}`}
                  >
                    {member.topResource.title}
                  </Link>
                </p>
              )}
            </RankingRow>
          ) : (
            <article className="analytics-ranking-item" key={institution!.slug}>
              <span aria-label="Unranked">—</span>
              <span className="analytics-member-logo">
                <img
                  src={
                    institution!.iconSrc ??
                    `/icons/${institution!.iconSlug}.svg`
                  }
                  alt=""
                  loading="lazy"
                />
              </span>
              <div className="analytics-ranking-copy">
                <h3>
                  {name}
                  {institution!.slug === 'university-of-southern-california'
                    ? ' (USC)'
                    : ''}
                </h3>
                <p>No data available for this reporting period.</p>
                <dl className="analytics-member-row-details">
                  {Object.entries(metrics).map(([key, label]) => (
                    <div key={key}>
                      <dt>{label}</dt>
                      <dd aria-label="Unavailable">—</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </article>
          )
        )}
        {!visible.length && (
          <p className="analytics-member-empty">
            No institutions match your search.
          </p>
        )}
      </div>
    </section>
  );
}
