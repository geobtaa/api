import { render } from '@testing-library/react';
import { expect, it } from 'vitest';
import { axeWithWCAG22 } from '../../test-utils/axe';

it('still reports WCAG failures when passing-node diagnostics are limited', async () => {
  const { container } = render(
    <main>
      <button />
      <img src="fixture.png" />
    </main>
  );
  const result = await axeWithWCAG22(container);
  expect(result.violations.map(({ id }) => id)).toEqual(
    expect.arrayContaining(['button-name', 'image-alt'])
  );
});
