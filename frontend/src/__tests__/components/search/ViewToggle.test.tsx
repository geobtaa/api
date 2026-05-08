import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ViewToggle } from '../../../components/search/ViewToggle';

describe('ViewToggle', () => {
  it('renders Map, List, and Gallery in order', () => {
    render(<ViewToggle currentView="map" onViewChange={vi.fn()} />);

    expect(
      screen.getAllByRole('button').map((button) => button.textContent)
    ).toEqual(['Map', 'List', 'Gallery']);
  });

  it('calls onViewChange with the selected view', async () => {
    const user = userEvent.setup();
    const onViewChange = vi.fn();

    render(<ViewToggle currentView="map" onViewChange={onViewChange} />);

    await user.click(screen.getByRole('button', { name: 'List view' }));

    expect(onViewChange).toHaveBeenCalledWith('list');
  });
});
