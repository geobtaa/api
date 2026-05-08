import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { GeoportalErrorPage } from '../../pages/ErrorPage';
import { getErrorPageContent } from '../../pages/errorPageContent';

function renderErrorPage(status: number) {
  render(
    <MemoryRouter>
      <GeoportalErrorPage status={status} />
    </MemoryRouter>
  );
}

describe('GeoportalErrorPage', () => {
  it.each([
    [401, 'Login required'],
    [403, 'Permission denied'],
    [404, 'Page not found'],
    [429, 'Rate limited'],
    [500, 'Something went wrong'],
    [502, 'Service unavailable'],
    [503, 'Service unavailable'],
    [504, 'Service unavailable'],
  ])('renders themed copy for %s', (status, title) => {
    renderErrorPage(status);

    expect(screen.getByText(`Error ${status}`)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
    expect(screen.getByText('BTAA Geoportal')).toBeInTheDocument();
  });

  it('uses a generic fallback for unexpected statuses', () => {
    expect(getErrorPageContent(418, "I'm a teapot")).toMatchObject({
      status: 418,
      title: "I'm a teapot",
      seoTitle: "418 I'm a teapot",
    });
  });
});
