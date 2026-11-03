import { test, expect, type Page } from '@playwright/test';
import { fixtureResponse } from './fixtures.mjs';
const image = (page: Page) =>
  page
    .getByTestId('selection')
    .evaluate((el) => JSON.parse(el.textContent || 'null'));
const opened = (page: Page, index = 0) =>
  expect.poll(async () => (await image(page))?.image?.index).toBe(index);
const full = (page: Page) =>
  page.getByRole('link', { name: 'Full Resolution', exact: true });

test.beforeEach(async ({ page }) => {
  page.on('pageerror', (error) => {
    throw error;
  });
  await page.route('**/*', (route) => {
    const url = new URL(route.request().url());
    const response = fixtureResponse(url);
    if (response)
      return route.fulfill({
        status: response.status ?? 200,
        contentType: response.type ?? 'text/plain',
        body: response.body,
      });
    // The production component's public basemap setting points here; keep this test offline.
    if (url.hostname === 'tiles.openfreemap.org')
      return route.fulfill({
        contentType: 'application/json',
        body: fixtureResponse(new URL('http://127.0.0.1/fixtures/style.json'))!
          .body,
      });
    if (
      url.origin === 'https://cdnjs.cloudflare.com' &&
      url.pathname.startsWith('/ajax/libs/openseadragon/6.1.1/images/')
    )
      return route.fulfill({
        contentType: 'image/png',
        body: fixtureResponse(
          new URL('http://127.0.0.1/fixtures/iiif/a/full/full/0/default.png')
        )!.body,
      });
    if (url.hostname !== '127.0.0.1' || url.pathname.includes('/api/'))
      throw new Error(`Unexpected service request: ${url.href}`);
    return route.continue();
  });
  await page.goto('/');
});

for (const scenario of ['good', 'v2', 'multi-image'])
  test(`${scenario}: Downloads and viewer follow each other`, async ({
    page,
  }) => {
    if (scenario !== 'good')
      await page
        .getByRole('combobox', { name: 'Fixture', exact: true })
        .selectOption(scenario);
    await opened(page);
    await expect(full(page)).toHaveAttribute(
      'href',
      /\/iiif\/a\/full\/full\/0\/default.jpg$/
    );
    const picker = page.getByRole('combobox', {
      name: 'Page or sheet (2)',
      exact: true,
    });
    await picker.selectOption('1');
    await opened(page, 1);
    await expect(full(page)).toHaveAttribute(
      'href',
      /\/iiif\/b\/full\/full\/0\/default.jpg$/
    );
    await page
      .locator('ogm-image')
      .filter({ visible: true })
      .locator('.prev')
      .click();
    await opened(page);
    await expect(picker).toHaveValue('0');
    await expect(full(page)).toHaveAttribute(
      'href',
      /\/iiif\/a\/full\/full\/0\/default.jpg$/
    );
    await expect(
      page.getByText('Image downloads could not be loaded.')
    ).toHaveCount(0);
    await expect(
      page.getByRole('link', { name: 'Publisher download' })
    ).toBeVisible();
  });

test('loading and failed pages never retain the previous image download', async ({
  page,
}) => {
  await page
    .getByRole('combobox', { name: 'Fixture', exact: true })
    .selectOption('later-fails');
  await opened(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/fixtures/iiif/bad/info.json', async (route) => {
    await gate;
    await route.fulfill({ status: 503, body: 'Unavailable' });
  });
  try {
    await page
      .getByRole('combobox', { name: 'Page or sheet (2)', exact: true })
      .selectOption('1');
    await expect(full(page)).toHaveCount(0);
    await expect.poll(async () => (await image(page))?.pageIndex).toBe(1);
  } finally {
    release();
  }
  await expect(
    page.locator('ogm-alerts').filter({ visible: true })
  ).toBeVisible();
  await expect(full(page)).toHaveCount(0);
  expect((await image(page)).resourceUrl).toContain('/manifest/later-fails');
});

test('initial manifest failure uses the opened single-image fallback', async ({
  page,
}) => {
  await page
    .getByRole('combobox', { name: 'Fixture', exact: true })
    .selectOption('first-fails');
  await expect(full(page)).toHaveAttribute(
    'href',
    /\/iiif\/single\/full\/full\/0\/default.jpg$/
  );
});

test('duplicates and record changes preserve the correct image identity', async ({
  page,
}) => {
  await page
    .getByRole('combobox', { name: 'Fixture', exact: true })
    .selectOption('duplicate');
  await opened(page);
  await page
    .getByRole('combobox', { name: 'Page or sheet (3)', exact: true })
    .selectOption('1');
  await opened(page, 1);
  expect((await image(page)).image.occurrence).toBe(1);
  await page
    .getByRole('combobox', { name: 'Fixture', exact: true })
    .selectOption('v2');
  await opened(page);
  expect((await image(page)).resourceId).toBe('v2');
  await expect(
    page.getByRole('combobox', { name: 'Page or sheet (2)', exact: true })
  ).toHaveValue('0');
});

test('map selection clears image downloads; ArcGIS owns feature inspection', async ({
  page,
}) => {
  await page
    .getByRole('combobox', { name: 'Fixture', exact: true })
    .selectOption('mixed');
  await opened(page);
  await page
    .locator('wa-tab')
    .filter({ hasText: 'ArcGIS Feature Layer' })
    .click();
  await expect(full(page)).toHaveCount(0);
  await expect.poll(() => image(page)).toBeNull();
  const canvas = page.locator('ogm-map canvas.maplibregl-canvas');
  await expect(canvas).toBeVisible();
  await expect(async () => {
    await canvas.click();
    await expect(page.locator('ogm-attributes')).toContainText(
      'Fixture region'
    );
  }).toPass();
  await expect(
    page.getByRole('link', { name: 'Publisher download' })
  ).toBeVisible();
});

test('location-only records unmount the viewer and clear image downloads', async ({
  page,
}) => {
  await opened(page);
  await page
    .getByRole('combobox', { name: 'Fixture', exact: true })
    .selectOption('location');
  await expect(page.locator('ogm-viewer')).toHaveCount(0);
  await expect(full(page)).toHaveCount(0);
  await expect.poll(() => image(page)).toBeNull();
});

for (const scenario of ['good', 'arcgis']) {
  for (const fallback of [false, true]) {
    test(`${scenario}: toolbar fullscreen fills the viewport (${fallback ? 'fallback' : 'native'})`, async ({
      page,
    }) => {
      if (fallback) {
        await page.evaluate(() => {
          HTMLElement.prototype.requestFullscreen = () =>
            Promise.reject(new Error('Fullscreen unavailable'));
        });
      }
      await page
        .getByRole('combobox', { name: 'Fixture', exact: true })
        .selectOption(scenario);
      const canvas = page
        .locator(
          scenario === 'arcgis'
            ? 'ogm-map canvas.maplibregl-canvas'
            : 'ogm-image #openseadragon > .openseadragon-container > .openseadragon-canvas'
        )
        .filter({ visible: true });
      await expect(canvas).toBeVisible();
      if (scenario === 'good') await opened(page);
      const viewer = await page.locator('ogm-viewer').elementHandle();
      await page
        .getByRole('button', { name: 'Fullscreen', exact: true })
        .click();
      await expect
        .poll(() => page.evaluate(() => Boolean(document.fullscreenElement)))
        .toBe(!fallback);
      await expect
        .poll(async () => {
          const box = await canvas.boundingBox();
          return box
            ? Math.abs(box.y + box.height - page.viewportSize()!.height)
            : 999;
        })
        .toBeLessThan(5);
      expect(
        await page
          .locator('ogm-viewer')
          .evaluate((el, previous) => el === previous, viewer)
      ).toBe(true);
      await page
        .getByRole('button', { name: 'Exit fullscreen', exact: true })
        .click();
      await expect
        .poll(() => page.evaluate(() => Boolean(document.fullscreenElement)))
        .toBe(false);
      await expect
        .poll(
          async () => (await page.locator('ogm-viewer').boundingBox())?.height
        )
        .toBe(600);
      await page
        .getByRole('button', { name: 'Fullscreen', exact: true })
        .click();
      if (fallback) await page.keyboard.press('Escape');
      else {
        await expect
          .poll(() => page.evaluate(() => Boolean(document.fullscreenElement)))
          .toBe(true);
        await page.evaluate(() => document.exitFullscreen());
      }
      await expect(
        page.getByRole('button', { name: 'Fullscreen', exact: true })
      ).toHaveAttribute('aria-pressed', 'false');
      await expect
        .poll(
          async () => (await page.locator('ogm-viewer').boundingBox())?.height
        )
        .toBe(600);
    });
  }
}
