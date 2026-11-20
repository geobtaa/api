export type ActivityEntry = {
  id: string;
  action: string;
  outcome: string;
  actor_display_name: string;
  occurred_at: string;
  resource_id?: string | null;
  reason?: string | null;
  details: { fields?: string[]; source_set_id?: string | null };
};
export function CompactActivity({ entries }: { entries: ActivityEntry[] }) {
  return (
    <div className="divide-y divide-border rounded-md border border-border">
      {entries.map((entry) => (
        <details key={entry.id} className="group">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm hover:bg-surface-subtle [&::-webkit-details-marker]:hidden">
            <span
              aria-hidden="true"
              className="text-text-muted group-open:rotate-90"
            >
              ›
            </span>
            <span className="min-w-0 flex-1 truncate font-medium">
              {(
                {
                  'source.created': 'Source created',
                  'source.updated': 'Source updated',
                  'set.migrated': 'Resources migrated to Set',
                  'set.created': 'Set created',
                  'set.updated': 'Set updated',
                  'set.deactivated': 'Set deactivated',
                  'set.activated': 'Set activated',
                  'set.retired': 'Set retired',
                  'set.restored': 'Set restored',
                  'set.representative_changed': 'Set representative changed',
                  'resources.imported': 'Resources imported',
                  'resource.created': 'Resource created',
                  'resource.updated': 'Resource updated',
                  'resource.associated':
                    entry.details.source_set_id === null
                      ? 'Resource assigned to Set'
                      : 'Managing Set changed',
                  'workflow.created': 'Workflow created',
                  'workflow.updated': 'Workflow updated',
                  'workflow.draft_created': 'Workflow draft created',
                  'workflow.activated': 'Workflow activated',
                  'validation.completed': 'Validation completed',
                  'review.completed': 'Review completed',
                  'harvest.completed': 'Harvest completed',
                } as Record<string, string>
              )[entry.action] ?? entry.action}
            </span>
            <time
              className="shrink-0 text-xs text-text-muted"
              dateTime={entry.occurred_at}
            >
              {new Date(entry.occurred_at).toLocaleString()}
            </time>
          </summary>
          <div className="px-3 pb-3 text-sm text-text-secondary">
            {entry.action === 'resource.associated' && entry.resource_id && (
              <p className="mb-1 break-all">Resource ID: {entry.resource_id}</p>
            )}
            <p className="mb-1">
              {entry.outcome} · {entry.actor_display_name}
            </p>
            <p className="m-0 whitespace-pre-wrap [overflow-wrap:anywhere]">
              {entry.reason ??
                entry.details.fields?.join(', ') ??
                'No additional details.'}
            </p>
          </div>
        </details>
      ))}
    </div>
  );
}
