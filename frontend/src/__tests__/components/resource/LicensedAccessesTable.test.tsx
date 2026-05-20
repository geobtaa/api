import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import {
  LicensedAccessesTable,
  type LicensedAccessItem,
} from '../../../components/resource/LicensedAccessesTable';
import { scheduleAnalyticsBatch } from '../../../services/analytics';

vi.mock('../../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
}));

describe('LicensedAccessesTable', () => {
  const licensedAccesses: LicensedAccessItem[] = [
    {
      institution_code: '01',
      institution_name: 'Indiana University',
      access_url: 'https://example.com/iu',
      legacy_friendlier_id: '999-0001',
    },
    {
      institution_code: 'MSU',
      institution_name: 'Michigan State University',
      access_url: 'https://example.com/msu',
      legacy_friendlier_id: '999-0001',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders licensed institution links', () => {
    render(<LicensedAccessesTable licensedAccesses={licensedAccesses} />);

    expect(screen.getByText('Licensed Resource')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /Indiana University/i })
    ).toHaveAttribute('href', 'https://example.com/iu');
    expect(
      screen.getByRole('link', { name: /Michigan State University/i })
    ).toHaveAttribute('href', 'https://example.com/msu');
  });

  it('tracks licensed access clicks', () => {
    render(
      <LicensedAccessesTable
        licensedAccesses={licensedAccesses}
        resourceId="999-0001"
        searchId="search-123"
      />
    );

    const accessLink = screen.getByRole('link', {
      name: /Indiana University/i,
    });
    accessLink.addEventListener('click', (event) => event.preventDefault());
    fireEvent.click(accessLink);

    expect(scheduleAnalyticsBatch).toHaveBeenCalledWith({
      events: [
        expect.objectContaining({
          event_type: 'licensed_access_click',
          search_id: 'search-123',
          resource_id: '999-0001',
          label: 'Indiana University',
          destination_url: 'https://example.com/iu',
          source_component: 'LicensedAccessesTable',
        }),
      ],
    });
  });

  it('does not render without licensed accesses', () => {
    const { container } = render(
      <LicensedAccessesTable licensedAccesses={[]} />
    );

    expect(container.firstChild).toBeNull();
  });
});
