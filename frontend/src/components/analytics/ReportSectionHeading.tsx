import type { ReactNode } from 'react';

export function ReportSectionHeading({
  title,
  description,
  id,
}: {
  title: string;
  description: ReactNode;
  id?: string;
}) {
  return (
    <header className="analytics-section-heading">
      <h2 id={id}>{title}</h2>
      <p>{description}</p>
    </header>
  );
}
