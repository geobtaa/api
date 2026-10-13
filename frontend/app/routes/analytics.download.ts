import { readFile } from 'node:fs/promises';
import path from 'node:path';
import type { LoaderFunctionArgs } from 'react-router';
import {
  analyticsHeaders,
  requireAnalyticsSession,
} from '../lib/analytics-auth.server';

export async function loader({ request, params }: LoaderFunctionArgs) {
  await requireAnalyticsSession(request);
  const resource = params['*'] ?? '';
  if (
    !/^(manifest\.json|(?:\d{4}-\d{2}|ay-\d{4}|all)\/[a-f0-9]{64}\/(?:report\.json|tables\.zip|evidence-[a-f0-9]{64}\.(?:json|zip)))$/.test(
      resource
    )
  ) {
    throw new Response('Report unavailable', {
      status: 404,
      headers: analyticsHeaders,
    });
  }
  try {
    const bytes = await readFile(
      path.resolve('private-analytics-reports', resource)
    );
    return new Response(bytes, {
      headers: {
        ...analyticsHeaders,
        'Content-Type': resource.endsWith('.zip')
          ? 'application/zip'
          : 'application/json',
        'Content-Disposition': `attachment; filename="${path.basename(resource)}"`,
        'X-Content-Type-Options': 'nosniff',
      },
    });
  } catch {
    throw new Response('Report unavailable', {
      status: 404,
      headers: analyticsHeaders,
    });
  }
}
