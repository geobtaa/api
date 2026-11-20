import { request, type Page } from '../api';
export { request, ApiError, type Page } from '../api';
export const setBase = '/api/v1/admin/sets';
export type SetRecord = {
  represented_by_id?: string | null;
  resource_count?: number;
  set_id: string;
  source_id: string;
  lock_version: number;
  updated_at: string;
  title: string;
  legacy_code: string;
  set_scope: string;
  status: string;
  description: string;
  endpoint_url: string | null;
  endpoint_description: string;
  workflow: string;
  workflow_catalog_id?: string | null;
  review_interval: string;
  harvest_interval: string;
  tags: string;
  admin_notes: string;
};
export type SetContract = {
  create: boolean;
  update: boolean;
  activity_read: boolean;
  workflow_read?: boolean;
  representative_update?: boolean;
  states?: string[];
  state_actions?: { current: string; target: string; label: string }[];
  fields: Record<
    string,
    {
      maxLength?: number;
      pattern?: string;
      enum?: string[];
      default?: string;
      description?: string;
    }
  >;
};

export type SetStatePreview = {
  set_id: string;
  title: string;
  current: string;
  target: string;
  lock_version: number;
  open_tasks: number;
  active_jobs?: number;
  managed_resources?: number;
  can_proceed: boolean;
  consequences: string[];
};

export async function loadImportSets(signal: AbortSignal) {
  const sets: SetRecord[] = [];
  let total = Infinity;
  while (sets.length < total) {
    const offset = sets.length ? '&offset=' + sets.length : '';
    const page = await request<Page<SetRecord>>(
      setBase + '?limit=500' + offset,
      { signal }
    );
    sets.push(...page.items);
    total = page.total;
    if (!page.items.length) break;
  }
  return sets.filter((set) => set.status !== 'retired');
}
