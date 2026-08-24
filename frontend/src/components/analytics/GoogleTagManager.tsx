import { useEffect, useRef } from 'react';
import { pushDataLayerEvent } from '../../services/analytics';

const GOOGLE_TAG_MANAGER_SCRIPT_ID = 'google-tag-manager';

interface GoogleTagManagerProps {
  containerId: string;
  locationKey?: string;
}

export function GoogleTagManager({
  containerId,
  locationKey,
}: GoogleTagManagerProps) {
  const previousPageLocationRef = useRef<string | null>(null);

  useEffect(() => {
    if (!containerId || document.getElementById(GOOGLE_TAG_MANAGER_SCRIPT_ID)) {
      return;
    }

    pushDataLayerEvent('gtm.js', {
      'gtm.start': new Date().getTime(),
    });

    const firstScript = document.getElementsByTagName('script')[0];
    const script = document.createElement('script');
    script.id = GOOGLE_TAG_MANAGER_SCRIPT_ID;
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(
      containerId
    )}`;

    if (firstScript?.parentNode) {
      firstScript.parentNode.insertBefore(script, firstScript);
    } else {
      document.head.appendChild(script);
    }
  }, [containerId]);

  useEffect(() => {
    const pageLocation = window.location.href;
    const previousPageLocation = previousPageLocationRef.current;
    previousPageLocationRef.current = pageLocation;

    // GTM handles the initial page view when its container loads. Only emit
    // this custom event for subsequent React Router navigations.
    if (
      previousPageLocation === null ||
      previousPageLocation === pageLocation
    ) {
      return;
    }

    pushDataLayerEvent('virtual_page_view', {
      page_location: pageLocation,
      page_path: `${window.location.pathname}${window.location.search}${window.location.hash}`,
      page_title: document.title,
      previous_page_location: previousPageLocation,
    });
  }, [locationKey]);

  return null;
}
