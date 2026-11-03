/**
 * Shared axe helper that targets WCAG 2.0, 2.1, and 2.2 Level A and AA rules.
 * Use this instead of calling axe() directly for consistent a11y coverage.
 */
import type AxeCore from 'axe-core';
import { axe } from 'vitest-axe';

const WCAG_22_RUN_ONLY = {
  type: 'tag' as const,
  values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'],
};

/**
 * Run axe accessibility checks with WCAG 2.2 AA rules.
 * @param element - DOM element or HTML string to test
 * @param options - Additional axe RunOptions (merged with WCAG 2.2 runOnly)
 * @returns Promise<AxeResults>
 */
export async function axeWithWCAG22(
  element: Element | string,
  options?: AxeCore.RunOptions
) {
  return axe(element, {
    runOnly: WCAG_22_RUN_ONLY,
    // Evaluate every rule/node, but avoid generating selectors for thousands of
    // passing table cells. Keep full violation and manual-review diagnostics.
    // https://github.com/dequelabs/axe-core/blob/develop/doc/API.md#use-resulttypes
    resultTypes: ['violations', 'incomplete'],
    ...options,
  });
}
