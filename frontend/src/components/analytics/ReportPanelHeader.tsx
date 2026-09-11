import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

export function ReportPanelHeader({
  title,
  icon: Icon,
  level = 3,
  children,
}: {
  title: string;
  icon: LucideIcon;
  level?: 2 | 3;
  children?: ReactNode;
}) {
  const Heading = level === 2 ? 'h2' : 'h3';
  return (
    <div className="analytics-panel-header analytics-report-panel-header">
      <div>
        <Icon aria-hidden="true" />
        <Heading>{title}</Heading>
      </div>
      {children && <div className="analytics-panel-actions">{children}</div>}
    </div>
  );
}
