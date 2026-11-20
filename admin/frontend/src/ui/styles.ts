/** Complete Tailwind class strings, shared by native controls and router links. */
export const ui = {
  navLink:
    'rounded-full px-3 py-2 text-sm font-medium text-white no-underline hover:bg-primary-hover aria-[current=page]:bg-surface aria-[current=page]:text-primary',
  page: 'mx-4 min-w-0 py-8 sm:mx-6 lg:mx-8 lg:py-10',
  intro: 'mb-6 max-w-3xl text-sm leading-6 text-text-secondary',
  backLink:
    'mb-5 inline-flex text-sm font-medium text-active hover:text-active-hover hover:underline',
  kicker: 'mb-2 text-xs font-semibold uppercase tracking-widest text-active',
  panel: 'rounded-lg border border-border bg-surface p-4 shadow-xs sm:p-6',
  form: 'my-6 rounded-lg border border-border bg-surface p-4 shadow-xs sm:p-6',
  field:
    'flex min-w-0 flex-col gap-2 text-sm font-medium text-text-primary [&_small]:font-normal [&_small]:leading-5 [&_small]:text-text-secondary',
  fieldGrid: 'grid grid-cols-1 items-start gap-6 md:grid-cols-2',
  checkbox: 'flex items-start gap-3 text-sm leading-6 [&_input]:mt-1',
  choice:
    'flex min-h-11 w-full items-center rounded-md border border-border bg-surface px-4 py-3 text-left text-sm text-active hover:border-active hover:bg-active-soft aria-pressed:border-active aria-pressed:bg-active-soft aria-pressed:font-semibold [overflow-wrap:anywhere]',
  toolbar:
    'my-5 flex flex-wrap items-center justify-between gap-3 [&>p]:mb-0 [&>label]:flex [&>label]:flex-wrap [&>label]:items-center [&>label]:gap-2',
  search:
    'my-5 rounded-lg border border-border bg-surface p-4 shadow-xs [&>label]:mb-2 [&>label]:block',
  inline:
    'flex min-w-0 flex-wrap items-center gap-2 [&>input]:min-w-0 [&>input]:flex-1',
  actions: 'mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-5',
  pagination:
    'mt-5 flex flex-wrap items-center gap-3 text-sm text-text-secondary',
  primary:
    'inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-full border border-transparent bg-primary px-4 py-2 text-sm font-semibold text-white no-underline shadow-xs transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none',
  secondary:
    'inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-full border border-border-strong bg-surface px-4 py-2 text-sm font-semibold text-text-primary no-underline shadow-xs transition-colors hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none',
  textAction:
    'inline-flex min-h-8 items-center rounded-md px-2 py-1 text-sm font-medium text-active hover:bg-active-soft hover:text-active-hover disabled:cursor-not-allowed disabled:opacity-50',
  badge:
    'inline-flex items-center rounded-md bg-active-soft px-2 py-1 text-xs font-semibold whitespace-nowrap text-primary ring-1 ring-primary/10 ring-inset',
  activeBadge:
    'inline-flex items-center rounded-md bg-success-soft px-2 py-1 text-xs font-semibold whitespace-nowrap text-success ring-1 ring-success/20 ring-inset',
  code: 'mt-1 block font-mono text-xs font-normal break-all text-text-secondary',
  tableRegion:
    'min-w-0 overflow-x-auto rounded-lg border border-border bg-surface shadow-xs',
  table:
    'w-full border-collapse text-left text-sm [&_th]:px-4 [&_th]:py-3 [&_th]:align-top [&_td]:px-4 [&_td]:py-3 [&_td]:align-top [&_thead]:border-b [&_thead]:border-border [&_thead]:bg-surface-subtle [&_thead_th]:font-semibold [&_thead_th]:whitespace-nowrap [&_tbody_tr]:border-b [&_tbody_tr]:border-border [&_tbody_tr:last-child]:border-0 [&_tbody_tr:hover]:bg-surface-subtle [&_tbody_th]:min-w-52 [&_tbody_th]:max-w-md [&_tbody_th]:font-medium [&_tbody_a]:text-active [&_tbody_a:hover]:underline [&_td]:text-text-secondary',
  notice:
    'my-5 rounded-lg border border-border bg-surface p-5 text-sm leading-6 [&>p:last-child]:mb-0',
  error:
    'my-5 rounded-lg border border-danger/30 bg-danger-soft p-5 text-sm leading-6 text-danger [&_h2]:text-base [&_button]:mt-3 [&_a]:underline',
  fieldError: 'text-xs font-normal text-danger empty:hidden',
  saved: 'min-h-6 text-sm font-medium text-success',
  comparison:
    'max-h-96 overflow-y-auto rounded-md border border-border bg-surface p-4 [&_div]:border-b [&_div]:border-border [&_div]:py-3 [&_dt]:font-semibold [&_dd]:mt-1 [&_dd]:whitespace-pre-wrap [&_dd]:[overflow-wrap:anywhere]',
  definitionList:
    'my-6 divide-y divide-border rounded-lg border border-border bg-surface px-5 [&>div]:grid [&>div]:gap-2 [&>div]:py-4 sm:[&>div]:grid-cols-[minmax(9rem,0.35fr)_1fr] sm:[&>div]:gap-6 [&_dt]:text-sm [&_dt]:font-semibold [&_dd]:min-w-0 [&_dd]:text-sm [&_dd]:leading-6 [&_dd]:text-text-secondary [&_dd]:[overflow-wrap:anywhere] [&_a]:text-active [&_a:hover]:underline',
  dialog:
    'm-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-xl border border-border bg-surface p-6 text-text-primary shadow-xl backdrop:bg-primary-dark/50',
  input:
    'block w-full min-w-0 rounded-md border-control bg-surface px-3 py-2.5 text-sm font-normal leading-5 text-text-primary shadow-xs placeholder:text-text-muted focus:border-active focus:ring-2 focus:ring-active/20 disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-text-secondary [&[readonly]]:bg-surface-muted aria-invalid:border-danger aria-invalid:focus:border-danger aria-invalid:focus:ring-danger/20',
} as const;
