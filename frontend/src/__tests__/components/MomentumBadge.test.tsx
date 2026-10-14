import { render, screen } from '@testing-library/react';
import { it, expect } from 'vitest';
import { MomentumBadge } from '../../components/analytics/MomentumBadge';

it.each([
  [15, 10, '+50.0%'],
  [5, 10, '-50.0%'],
  [10, 10, '0.0%'],
  [5, 0, 'No prior activity'],
  [5, null, 'Unavailable'],
] as const)(
  'formats %s against %s without inventing a baseline',
  (value, previous, text) => {
    render(<MomentumBadge value={value} previous={previous} label="views" />);
    expect(screen.getByText(text)).toBeInTheDocument();
  }
);
