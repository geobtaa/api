import { LockKeyhole } from 'lucide-react';

interface RestrictedAccessIndicatorProps {
  className?: string;
  iconClassName?: string;
  showLabel?: boolean;
}

function classes(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ');
}

export function RestrictedAccessIndicator({
  className,
  iconClassName,
  showLabel = false,
}: RestrictedAccessIndicatorProps) {
  const label = 'Restricted access';

  return (
    <span
      className={classes(
        'inline-flex shrink-0 items-center justify-center border border-amber-300 bg-amber-50 text-amber-700',
        showLabel
          ? 'gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold'
          : 'h-5 w-5 rounded-full',
        className
      )}
      aria-label={label}
      role={showLabel ? undefined : 'img'}
      title={label}
    >
      <LockKeyhole
        className={classes('h-3.5 w-3.5', iconClassName)}
        aria-hidden="true"
      />
      {showLabel ? <span>Restricted</span> : null}
    </span>
  );
}
