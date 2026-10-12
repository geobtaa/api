import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

export function MetricHeading({
  icon: Icon,
  children,
  level = 3,
}: {
  icon: LucideIcon;
  children: ReactNode;
  level?: 2 | 3;
}) {
  const Heading = level === 2 ? 'h2' : 'h3';
  return (
    <Heading className="analytics-widget-heading">
      <Icon size={20} aria-hidden="true" />
      <span>{children}</span>
    </Heading>
  );
}
