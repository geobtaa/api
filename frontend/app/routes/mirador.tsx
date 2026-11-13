import { redirect, type LoaderFunctionArgs } from 'react-router';

/** Preserve bookmarked manifest URLs while retiring the Mirador renderer. */
export function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  return redirect(`/ogm-viewer${url.search}`, 301);
}
