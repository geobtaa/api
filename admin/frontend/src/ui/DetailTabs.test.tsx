import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { DetailTabs } from './DetailTabs';
import { CompactActivity } from './CompactActivity';
it('supports keyboard tab selection and expandable activity details', () => {
  render(
    <DetailTabs
      tabs={[
        {
          label: 'Activity Log',
          content: (
            <CompactActivity
              entries={[
                {
                  id: '1',
                  action: 'source.updated',
                  outcome: 'succeeded',
                  actor_display_name: 'Steward',
                  occurred_at: '2026-09-23T12:00:00Z',
                  reason: 'Corrected endpoint',
                  details: {},
                },
              ]}
            />
          ),
        },
        { label: 'Resources', content: <p>Browse maps</p> },
      ]}
    />
  );
  expect(
    screen.getByText('Corrected endpoint').closest('details')
  ).not.toHaveAttribute('open');
  fireEvent.click(screen.getByText('Source updated'));
  expect(
    screen.getByText('Corrected endpoint').closest('details')
  ).toHaveAttribute('open');
  fireEvent.keyDown(screen.getByRole('tab', { name: 'Activity Log' }), {
    key: 'ArrowRight',
  });
  expect(screen.getByRole('tab', { name: 'Resources' })).toHaveFocus();
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Browse maps');
});
