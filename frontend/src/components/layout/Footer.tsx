import React, { Suspense, useEffect, useState } from 'react';

interface FooterProps {
  id?: string;
}

const FooterClient = React.lazy(() => import('./Footer.client'));

export function Footer(props: FooterProps) {
  // Prevent hydration mismatches: render deterministic placeholder on the server
  // and on the client's first render. Then swap in the client-only footer after mount.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <div className="text-gray-500" aria-hidden="true">
        Loading…
      </div>
    );
  }

  return (
    <Suspense fallback={null}>
      <FooterClient {...props} />
    </Suspense>
  );
}
