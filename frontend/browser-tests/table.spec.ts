import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('Parquet range reads, exact values, literal search, sorting and pagination', async ({
  page,
}) => {
  const data = fs.readFileSync(
    path.resolve('browser-tests/fixtures/table.parquet')
  );
  const reads: number[] = [];
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/fixtures/table.parquet', async (route) => {
    const range = (await route.request().allHeaders()).range;
    const headers = {
      'Content-Type': 'application/vnd.apache.parquet',
      'Accept-Ranges': 'bytes',
      'Content-Length': String(data.length),
    };
    if (route.request().method() === 'HEAD')
      return route.fulfill({
        status: range ? 206 : 200,
        headers: {
          ...headers,
          ...(range
            ? { 'Content-Range': `bytes 0-${data.length - 1}/${data.length}` }
            : {}),
        },
        body: '',
      });
    if (range) {
      const [, start, end] = /bytes=(\d+)-(\d*)/.exec(range)!;
      const first = Number(start),
        last = end ? Number(end) : data.length - 1;
      const body = data.subarray(first, last + 1);
      reads.push(body.length);
      return route.fulfill({
        status: 206,
        headers: {
          ...headers,
          'Content-Length': String(body.length),
          'Content-Range': `bytes ${first}-${last}/${data.length}`,
        },
        body,
      });
    }
    return route.fulfill({ headers, body: data });
  });
  await page.goto('/table.html');
  await expect(page.getByText('120,000 matching rows')).toBeVisible({
    timeout: 30000,
  });
  await expect(
    page.getByRole('cell', { name: '00000', exact: true })
  ).toBeVisible();
  await expect(
    page.getByRole('cell', { name: '9007199254740993', exact: true })
  ).toBeVisible();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByText('Page 2 of 2400')).toBeVisible();
  await page.getByRole('searchbox').fill("O'Brien");
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('1 matching rows')).toBeVisible();
  await expect(
    page.getByRole('cell', { name: "O'Brien", exact: true })
  ).toBeVisible();
  await page.getByRole('searchbox').fill("' OR true --");
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('0 matching rows')).toBeVisible();
  await page.getByRole('searchbox').fill('');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('120,000 matching rows')).toBeVisible();
  await page.getByRole('button', { name: 'amount', exact: true }).click();
  await expect(
    page.getByText('Loading table…', { exact: false })
  ).toBeVisible();
  await expect(page.getByText('120,000 matching rows')).toBeVisible();
  await expect(
    page.getByRole('columnheader', { name: 'amount ↑' })
  ).toHaveAttribute('aria-sort', 'ascending');
  await expect(
    page.locator('tbody tr').first().locator('td').nth(2)
  ).toHaveText('2');
  expect(reads.some((bytes) => bytes < data.length)).toBeTruthy();
  expect(errors).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath('table.png'),
    fullPage: true,
  });
});

test('unavailable assets have an explicit retry state', async ({ page }) => {
  await page.route('**/fixtures/table.parquet', (route) =>
    route.fulfill({ status: 404, body: '' })
  );
  await page.goto('/table.html');
  await expect(
    page.getByText(
      'Table preview unavailable. Retry or use the original download.'
    )
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Retry', exact: true })
  ).toBeVisible();
});

test('users can cancel loading without freezing the page', async ({ page }) => {
  await page.route('**/fixtures/table.parquet', () => new Promise(() => {}));
  await page.goto('/table.html');
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(
    page.getByText('Table query cancelled. Retry to continue.')
  ).toBeVisible();
  await page.getByRole('searchbox').fill('Page remains responsive');
});
