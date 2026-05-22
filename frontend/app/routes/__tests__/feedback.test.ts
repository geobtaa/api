import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ActionFunctionArgs } from 'react-router';
import { action } from '../feedback';
import { serverFetch } from '../../lib/server-api';

vi.mock('../../lib/server-api', () => ({
  serverFetch: vi.fn(),
}));

function feedbackRequest(fields: Record<string, string>) {
  return new Request('https://geo.example.org/feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      referer: 'https://geo.example.org/feedback',
      'user-agent': 'vitest',
    },
    body: new URLSearchParams(fields),
  });
}

describe('feedback route action', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts valid feedback to the API endpoint', async () => {
    vi.mocked(serverFetch).mockResolvedValue(
      new Response(JSON.stringify({ data: { id: 'submitted' } }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const result = await action({
      request: feedbackRequest({
        name: 'Ada',
        email_address: 'ada@example.edu',
        topic: 'Question',
        description: 'Can someone follow up?',
        contact_info: '',
      }),
      params: {},
    } as unknown as ActionFunctionArgs);

    expect(serverFetch).toHaveBeenCalledTimes(1);
    const [endpoint, options] = vi.mocked(serverFetch).mock.calls[0];
    expect(endpoint).toBe('/feedback');
    expect(options?.method).toBe('POST');
    expect(JSON.parse(String(options?.body))).toMatchObject({
      name: 'Ada',
      email_address: 'ada@example.edu',
      topic: 'Question',
      description: 'Can someone follow up?',
      source_url: 'https://geo.example.org/feedback',
      user_agent: 'vitest',
    });
    expect(result).toEqual({
      status: 'success',
      message: 'Thank you for your feedback. Your message has been sent.',
    });
  });

  it('returns field errors before posting invalid feedback', async () => {
    const result = await action({
      request: feedbackRequest({
        topic: '',
        description: '',
      }),
      params: {},
    } as unknown as ActionFunctionArgs);

    expect(serverFetch).not.toHaveBeenCalled();
    expect(result).toMatchObject({
      status: 'error',
      message: 'Please review the highlighted fields.',
      fieldErrors: {
        topic: 'Select a feedback topic.',
        description: 'Enter your feedback.',
      },
    });
  });

  it('returns the API error message when delivery fails', async () => {
    vi.mocked(serverFetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          message: 'Feedback delivery is temporarily unavailable.',
        }),
        {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        }
      )
    );

    const result = await action({
      request: feedbackRequest({
        topic: 'Question',
        description: 'Can someone follow up?',
      }),
      params: {},
    } as unknown as ActionFunctionArgs);

    expect(result).toMatchObject({
      status: 'error',
      message: 'Feedback delivery is temporarily unavailable.',
    });
  });
});
