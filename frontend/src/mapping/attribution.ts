import type { Map } from 'maplibre-gl';

/** Collapse once attribution arrives; subsequent opening/closing belongs to the user. */
export function collapseInitialAttribution(
  map: Pick<Map, 'getContainer' | 'on' | 'off'>
) {
  const cleanup = () => {
    map.off('styledata', collapse);
    map.off('sourcedata', collapse);
  };
  const collapse = () => {
    const details = map
      .getContainer()
      .querySelector<HTMLDetailsElement>(
        '.maplibregl-ctrl-attrib.maplibregl-compact:not(.maplibregl-attrib-empty)'
      );
    if (!details) return;
    details.removeAttribute('open');
    details.classList.remove('maplibregl-compact-show');
    cleanup();
  };
  map.on('styledata', collapse);
  map.on('sourcedata', collapse);
  collapse();
  return cleanup;
}
