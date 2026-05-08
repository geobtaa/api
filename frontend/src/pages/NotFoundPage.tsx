import { GeoportalErrorPage } from './ErrorPage';

export function NotFoundPage() {
  return <GeoportalErrorPage status={404} />;
}
