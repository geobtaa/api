import { redirect } from 'react-router';

export function loader() {
  if (!import.meta.env.DEV) {
    throw redirect('/');
  }

  return null;
}

export default function TurnstilePreviewRoute() {
  return null;
}
