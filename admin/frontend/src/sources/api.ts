export { request, ApiError, type Page } from '../api';
export const sourceBase = '/api/v1/admin/sources';
export type Source = {
  source_id: string;
  legacy_code?: string | null;
  title: string;
  description: string;
  landing_page: string | null;
  admin_notes: string;
  lock_version: number;
  updated_at: string;
};
export type SourceContract = {
  create: boolean;
  update: boolean;
  activity_read: boolean;
  resource_read: boolean;
  set_read?: boolean;
  fields: Record<string, { maxLength?: number; pattern?: string }>;
};
export function sourceResources(id: string) {
  return new URLSearchParams({ filters: JSON.stringify({ source: [id] }) });
}
