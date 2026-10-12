import { MomentumBadge } from './MomentumBadge';
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { ArrowUpRight } from 'lucide-react';
import { RankNumber } from './RankNumber';

export function RankingRow({
  rank,
  title,
  href,
  thumbnail,
  description,
  subtitle,
  kicker,
  value,
  label,
  maximum,
  secondary,
  previousValue,
  children,
}: {
  children?: ReactNode;
  rank: number;
  title: string;
  href?: string;
  thumbnail?: ReactNode;
  description?: string;
  subtitle?: ReactNode;
  kicker?: ReactNode;
  value: number;
  label: string;
  maximum: number;
  secondary?: { value: number | null; label: string };
  previousValue?: number | null;
}) {
  const number = new Intl.NumberFormat('en-US');
  return (
    <article
      className={`analytics-ranking-item${rank === 1 ? ' analytics-ranking-row--leader' : ''}`}
    >
      <RankNumber rank={rank} />
      {thumbnail}
      <div className="analytics-ranking-copy">
        {kicker && <div className="analytics-ranking-kicker">{kicker}</div>}
        <h3>{href ? <Link to={href}>{title}</Link> : title}</h3>
        {subtitle}
        {description && <p>{description}</p>}
        <div className="analytics-collection-track" aria-hidden="true">
          <i style={{ width: `${(value / Math.max(1, maximum)) * 100}%` }} />
        </div>
        {children}
      </div>
      <div className="analytics-ranking-metrics">
        <div className="analytics-ranking-stat">
          <strong>{number.format(value)}</strong>
          <span>{label}</span>
        </div>
        {secondary && (
          <div className="analytics-ranking-stat">
            <strong>
              {secondary.value == null ? '—' : number.format(secondary.value)}
            </strong>
            <span>{secondary.label}</span>
          </div>
        )}
        {previousValue !== undefined && (
          <div className="analytics-ranking-trend">
            <MomentumBadge
              value={value}
              previous={previousValue}
              label={label}
            />
          </div>
        )}
      </div>
      {href && (
        <Link
          to={href}
          className="analytics-row-action"
          aria-label={`Open ${title}`}
        >
          <ArrowUpRight size={16} aria-hidden />
        </Link>
      )}
    </article>
  );
}
