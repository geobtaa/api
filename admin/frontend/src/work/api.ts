export { request, ApiError } from '../api';
export const taskBase = '/api/v1/admin/tasks';
export type Task = {
  task_id: string;
  set_id: string;
  set_title: string;
  source_id: string;
  source_title: string;
  work_type: string;
  title: string;
  description: string;
  status: string;
  due_on: string;
  planned_on: string | null;
  assignee_id: string | null;
  assignee_name: string | null;
  recurring: boolean;
  predecessor_id: string | null;
  lock_version: number;
  created_at: string;
  completed_at: string | null;
  completion_recorded_at: string | null;
  completed_by_name: string | null;
  completion_summary: string | null;
  evidence: { label: string; url: string }[];
  processed_count: number;
  changed_count: number;
};
export type TaskPage = {
  items: Task[];
  total: number;
  offset: number;
  limit: number;
};
export type WorkContract = {
  create: boolean;
  update: boolean;
  complete: boolean;
  configure: boolean;
  report: boolean;
  work_types: string[];
  statuses: string[];
};
export type Period = {
  period_id: string;
  name: string;
  starts_on: string;
  ends_on: string;
};
export type Report = {
  completed: number;
  processed: number;
  changed: number;
  late: number;
  total_groups: number;
  offset: number;
  limit: number;
  groups: {
    key: string;
    label: string;
    completed: number;
    processed: number;
    changed: number;
    late: number;
  }[];
};
export type Maintenance = {
  next_due_on: string | null;
  set_id: string;
  work_type: string;
  interval: string;
  enabled: boolean;
  assignee_id: string | null;
  lock_version: number;
};
export type Assignee = { actor_id: string; display_name: string };
export type TaskEvents = {
  items: {
    event_id: string;
    action: string;
    actor_name: string;
    recorded_at: string;
    occurred_at: string;
    details: Record<string, unknown>;
  }[];
  total: number;
  offset: number;
  limit: number;
};
export const today = () => new Date().toISOString().slice(0, 10);
export const monthBounds = (month: string) => {
  const [year, number] = month.split('-').map(Number);
  return [
    month + '-01',
    `${month}-${new Date(Date.UTC(year, number, 0)).getUTCDate()}`,
  ];
};
