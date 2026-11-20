export const appUrl = (path: string) =>
  import.meta.env.BASE_URL.replace(/\/$/, '') + path;

export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public code = 'unavailable',
    public fields: { field: string; message: string }[] = []
  ) {
    super(message);
  }
}

export async function request<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(appUrl(url), {
      ...options,
      credentials: 'same-origin',
      headers: { Accept: 'application/json', ...options?.headers },
    });
  } catch {
    throw new ApiError(
      'The API could not be reached. Your changes are still here; retry to confirm the result.'
    );
  }
  if (response.ok) return response.json() as Promise<T>;
  if (response.status === 401)
    throw new ApiError('Sign in to continue.', 'unauthenticated');
  if (response.status === 403)
    throw new ApiError(
      'You do not have permission for this action.',
      'forbidden'
    );
  if (response.status === 404)
    throw new ApiError(
      'This record is unavailable or outside your access.',
      'not_found'
    );
  const body = await response.json().catch(() => ({}));
  const issues = body.detail?.errors ?? body.detail;
  if (Array.isArray(issues) && issues.length) {
    const fields = issues.map(
      (item: { loc: (string | number)[]; msg: string }) => ({
        field: item.loc.slice(1).join('.'),
        message: item.msg,
      })
    );
    throw new ApiError(
      'Check the highlighted fields. Your changes have not been saved.',
      'validation',
      fields
    );
  }
  throw new ApiError(
    body.detail?.message ??
      'The request could not be completed. Retry to confirm the result.',
    body.detail?.code
  );
}
