import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TurnstileGate } from '../../../components/security/TurnstileGate';
import * as turnstileService from '../../../services/turnstile';

const widgetCallbacks = vi.hoisted(() => ({
  onSuccess: undefined as undefined | ((token: string) => Promise<void>),
  onError: undefined as undefined | (() => void),
}));

vi.mock('@marsidev/react-turnstile', async () => {
  const { forwardRef } = await import('react');
  return {
    Turnstile: forwardRef<
      HTMLDivElement,
      {
        options?: { appearance?: string };
        onSuccess: (token: string) => Promise<void>;
        onError: () => void;
      }
    >(function MockTurnstile({ options, onSuccess, onError }, ref) {
      widgetCallbacks.onSuccess = onSuccess;
      widgetCallbacks.onError = onError;
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

vi.mock('../../../services/turnstile', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../services/turnstile')>()),
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

describe('Turnstile verification recovery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(turnstileService.isTurnstileConfigured).mockReturnValue(true);
    vi.mocked(turnstileService.fetchTurnstileStatus).mockResolvedValue(false);
    vi.mocked(turnstileService.verifyTurnstileToken).mockResolvedValue(
      undefined
    );
  });

  it('stops after a failed verification and obtains a fresh challenge only on retry', async () => {
    vi.mocked(turnstileService.verifyTurnstileToken).mockRejectedValue(
      new Error('Verification unavailable')
    );
    render(<TurnstileGate>Protected app</TurnstileGate>);
    await screen.findByTestId('turnstile-widget');
    await act(() => widgetCallbacks.onSuccess!('single-use-token'));
    expect(screen.getByText('Verification unavailable')).toBeInTheDocument();
    expect(screen.queryByTestId('turnstile-widget')).not.toBeInTheDocument();
    expect(turnstileService.verifyTurnstileToken).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByTestId('turnstile-widget')).toBeInTheDocument();
    expect(turnstileService.fetchTurnstileStatus).toHaveBeenCalledTimes(2);
  });

  it('recovers an already-established session without redeeming another token', async () => {
    vi.mocked(turnstileService.verifyTurnstileToken).mockRejectedValue(
      new Error('Connection lost')
    );
    render(<TurnstileGate>Protected app</TurnstileGate>);
    await screen.findByTestId('turnstile-widget');
    await act(() => widgetCallbacks.onSuccess!('single-use-token'));
    vi.mocked(turnstileService.fetchTurnstileStatus).mockResolvedValue(true);
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Protected app')).toBeInTheDocument();
    expect(turnstileService.verifyTurnstileToken).toHaveBeenCalledTimes(1);
  });

  it('does not submit overlapping success callbacks', async () => {
    let resolve!: () => void;
    vi.mocked(turnstileService.verifyTurnstileToken).mockReturnValue(
      new Promise<void>((done) => {
        resolve = done;
      })
    );
    render(<TurnstileGate>Protected app</TurnstileGate>);
    await screen.findByTestId('turnstile-widget');
    let first!: Promise<void>;
    act(() => {
      first = widgetCallbacks.onSuccess!('same-token');
    });
    await act(() => widgetCallbacks.onSuccess!('same-token'));
    expect(turnstileService.verifyTurnstileToken).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolve();
      await first;
    });
    expect(screen.getByText('Protected app')).toBeInTheDocument();
  });

  it('shows a cooldown instead of a challenge when status is rate limited', async () => {
    vi.mocked(turnstileService.fetchTurnstileStatus).mockRejectedValue(
      new turnstileService.TurnstileVerificationError('Please wait', [], 30)
    );
    render(<TurnstileGate>Protected app</TurnstileGate>);
    expect(
      await screen.findByRole('button', { name: 'Try again in 30 seconds' })
    ).toBeDisabled();
    expect(screen.queryByTestId('turnstile-widget')).not.toBeInTheDocument();
  });
});
