import type { LoaderFunctionArgs } from 'react-router';
import { redirect } from 'react-router';

export function loader({ params, request }: LoaderFunctionArgs) {
  const { id } = params;

  if (!id) {
    throw new Response('Resource ID is required', { status: 400 });
  }

  const url = new URL(request.url);
  return redirect(`/resources/${id}${url.search}`, 301);
}
