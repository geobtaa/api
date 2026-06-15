import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TurnstileGate } from '../../../components/security/TurnstileGate';
import * as turnstileService from '../../../services/turnstile';

vi.mock('@marsidev/react-turnstile', async () => {
  const { forwardRef } = await import('react');
  return {
    Turnstile: forwardRef<
      HTMLDivElement,
      { options?: { appearance?: string } }
    >(function MockTurnstile({ options }, ref) {
      return (
        <div
          ref={ref}
          data-appearance={options?.appearance}
          data-testid="turnstile-widget"
        />
      );
    }),
  };
});

vi.mock('../../../services/turnstile', () => ({
  TURNSTILE_REQUIRED_EVENT: 'btaa:turnstile-required',
  clearTurnstileSessionToken: vi.fn(),
  fetchTurnstileStatus: vi.fn(),
  getTurnstileAction: vi.fn(),
  getTurnstileSiteKey: vi.fn(),
  isTurnstileConfigured: vi.fn(),
  verifyTurnstileToken: vi.fn(),
}));

describe('TurnstileGate', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(turnstileService.getTurnstileAction).mockReturnValue('search');
    vi.mocked(turnstileService.getTurnstileSiteKey).mockReturnValue('site-key');
    vi.mocked(turnstileService.fetchTurnstileStatus).mockResolvedValue(false);
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('renders children directly when Turnstile is not configured', () => {
    vi.mocked(turnstileService.isTurnstileConfigured).mockReturnValue(false);

    render(
      <TurnstileGate>
        <div>Geoportal app</div>
      </TurnstileGate>
    );

    expect(screen.getByText('Geoportal app')).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', {
        name: /before entering the btaa geoportal/i,
      })
    ).not.toBeInTheDocument();
  });

  it('renders the branded BTAA Geoportal gate when a challenge is required', async () => {
    vi.mocked(turnstileService.isTurnstileConfigured).mockReturnValue(true);

    render(
      <TurnstileGate>
        <div>Geoportal app</div>
      </TurnstileGate>
    );

    expect(
      screen.getByRole('heading', {
        name: /before entering the btaa geoportal/i,
      })
    ).toBeInTheDocument();
    expect(screen.getByAltText(/btaa geoportal logo/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /complete the verification check to continue to the btaa geoportal/i
      )
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/maps, datasets, imagery, and geospatial records/i)
    ).not.toBeInTheDocument();
    expect(await screen.findByTestId('turnstile-widget')).toHaveAttribute(
      'data-appearance',
      'always'
    );
    expect(screen.queryByText('Geoportal app')).not.toBeInTheDocument();
  });

  it('reopens the gate when a later API request requires verification', async () => {
    vi.mocked(turnstileService.isTurnstileConfigured).mockReturnValue(true);
    vi.mocked(turnstileService.fetchTurnstileStatus).mockResolvedValue(true);

    render(
      <TurnstileGate>
        <div>Geoportal app</div>
      </TurnstileGate>
    );

    expect(await screen.findByText('Geoportal app')).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(
        new CustomEvent(turnstileService.TURNSTILE_REQUIRED_EVENT)
      );
    });

    expect(turnstileService.clearTurnstileSessionToken).toHaveBeenCalled();
    expect(
      screen.getByRole('heading', {
        name: /before entering the btaa geoportal/i,
      })
    ).toBeInTheDocument();
    expect(screen.queryByText('Geoportal app')).not.toBeInTheDocument();
  });

  it('renders a mock verification control for the dev preview gate', async () => {
    vi.mocked(turnstileService.isTurnstileConfigured).mockReturnValue(false);
    const assign = vi.fn();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, assign },
    });

    render(
      <TurnstileGate devPreview>
        <div>Geoportal app</div>
      </TurnstileGate>
    );

    expect(
      screen.getByText(/local preview uses a mock verification control/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/local preview control/i)).toBeInTheDocument();
    expect(screen.queryByTestId('turnstile-widget')).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: /continue to the btaa geoportal/i })
    );

    expect(assign).toHaveBeenCalledWith('/');
  });
});
