import type { MetaFunction } from 'react-router';
import { MiradorViewerPage } from '../../src/pages/MiradorViewerPage';

export const meta: MetaFunction = () => [
  { title: 'Mirador Viewer' },
  { name: 'robots', content: 'noindex,nofollow' },
];

export default function MiradorRoute() {
  return <MiradorViewerPage />;
}
