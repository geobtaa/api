import type { Map } from 'maplibre-gl';
import { addPaneLayer } from '../../mapping/panes';

const PIN_IMAGE = 'featured-point-pin';

function pinImage() {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 88;
  const context = canvas.getContext('2d')!;
  context.scale(2, 2);
  context.shadowColor = '#0006';
  context.shadowBlur = 3;
  context.shadowOffsetX = 2;
  context.shadowOffsetY = 2;
  context.beginPath();
  context.moveTo(16, 41);
  context.bezierCurveTo(13, 34, 4, 23, 4, 15);
  context.bezierCurveTo(4, -1, 28, -1, 28, 15);
  context.bezierCurveTo(28, 23, 19, 34, 16, 41);
  const gradient = context.createLinearGradient(4, 5, 28, 35);
  gradient.addColorStop(0, '#50afd9');
  gradient.addColorStop(1, '#237eae');
  context.fillStyle = gradient;
  context.fill();
  context.shadowColor = 'transparent';
  context.strokeStyle = '#216b97';
  context.lineWidth = 1;
  context.stroke();
  context.beginPath();
  context.arc(16, 15, 4.5, 0, Math.PI * 2);
  context.fillStyle = 'white';
  context.fill();
  return context.getImageData(0, 0, 64, 88);
}

/** Keep OGM's data loading, replacing only homepage point presentation with pins. */
export function addFeaturedPins(map: Map, layerIds: string[]) {
  const pins: string[] = [];
  const circles: string[] = [];
  for (const id of layerIds) {
    const layer = map.getStyle().layers.find((layer) => layer.id === id);
    if (!layer || layer.type !== 'circle' || id.includes('selected')) continue;
    if (!map.hasImage(PIN_IMAGE))
      map.addImage(PIN_IMAGE, pinImage(), { pixelRatio: 2 });
    const pinId = `${id}-featured-pins`;
    addPaneLayer(
      map,
      {
        id: pinId,
        type: 'symbol',
        source: layer.source,
        ...('source-layer' in layer
          ? { 'source-layer': layer['source-layer'] }
          : {}),
        ...(layer.filter ? { filter: layer.filter } : {}),
        minzoom: layer.minzoom,
        maxzoom: layer.maxzoom,
        layout: {
          'icon-image': PIN_IMAGE,
          'icon-anchor': 'bottom',
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      },
      420
    );
    map.setLayoutProperty(id, 'visibility', 'none');
    circles.push(id);
    pins.push(pinId);
  }
  return () => {
    for (const id of pins) if (map.getLayer(id)) map.removeLayer(id);
    for (const id of circles)
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'visible');
  };
}
