import { test, expect } from '@playwright/test';

const polygon = (w: number, e: number, s: number, n: number) => ({
  type: 'Feature',
  properties: {},
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [w, s],
        [e, s],
        [e, n],
        [w, n],
        [w, s],
      ],
    ],
  },
});

test('real viewer fits source coverage across the antimeridian without foreign bounds objects', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => {
    errors.push(error.message);
    console.error(error.stack);
  });
  await page.route('**/fixtures/framing.json', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'FeatureCollection',
        features: [
          polygon(134, 135, -15, -14),
          polygon(-53, -52, 83, 84),
          polygon(-130, -90, 30, 50),
        ],
      }),
    })
  );
  await page.route('https://tiles.openfreemap.org/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        version: 8,
        sources: {},
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: { 'background-color': '#eef2f6' },
          },
        ],
      }),
    })
  );
  await page.goto('/?fixture=framing');
  await page
    .getByRole('combobox', { name: 'Fixture', exact: true })
    .selectOption('framing');
  const map = page.locator('ogm-map').filter({ visible: true });
  await expect(map).toHaveCount(1);
  await expect
    .poll(async () =>
      map.evaluate(async (el) => {
        try {
          const element = el as HTMLElement & {
            testMap?: import('maplibre-gl').Map;
            easeMapTo(options: object): Promise<import('maplibre-gl').Map>;
          };
          element.testMap ??= await element.easeMapTo({ duration: 0 });
          return element.testMap.loaded();
        } catch {
          return false;
        }
      })
    )
    .toBe(true);
  const camera = await map.evaluate((el) => {
    const m = (el as HTMLElement & { testMap: import('maplibre-gl').Map })
      .testMap;
    return {
      lng: m.getCenter().lng,
      sources: Object.keys(m.getStyle().sources),
      features: m.queryRenderedFeatures(m.project([-110, 40])).length,
    };
  });
  expect(((camera.lng + 540) % 360) - 180).toBeCloseTo(-139, 0);
  expect(camera.sources.length).toBeGreaterThan(0);
  expect(camera.features).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});
