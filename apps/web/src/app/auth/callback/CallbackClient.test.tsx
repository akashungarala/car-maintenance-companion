/**
 * UX-002 acceptance criteria.
 *
 * See docs/ux/ux-002-magic-link-callback.md.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '../../../mocks/node';
import { CallbackClient } from './CallbackClient';

const ENDPOINT = '/apps/car-maintenance-companion/api/auth/session';

const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace }) }));

describe('CallbackClient', () => {
  it('exchanges the token without any user action', async () => {
    const seen: string[] = [];
    server.use(
      http.post(ENDPOINT, async ({ request }) => {
        seen.push(((await request.json()) as { token: string }).token);
        return HttpResponse.json({ status: 'signed_in' });
      }),
    );

    render(<CallbackClient token="tok-abc" />);

    // No button, no click. A scanner issuing a GET spends nothing; a real
    // visitor waits a few hundred milliseconds and is through.
    await waitFor(() => expect(seen).toEqual(['tok-abc']));
  });

  it('navigates onward once signed in', async () => {
    replace.mockClear();
    server.use(http.post(ENDPOINT, () => HttpResponse.json({ status: 'signed_in' })));

    render(<CallbackClient token="tok-abc" />);

    await waitFor(() => expect(replace).toHaveBeenCalled());
  });

  it('shows the generic message when the link cannot be used', async () => {
    server.use(http.post(ENDPOINT, () => HttpResponse.json({}, { status: 401 })));

    render(<CallbackClient token="spent" />);

    expect(await screen.findByRole('heading', { name: /cannot be used/i })).toBeInTheDocument();
  });

  it('shows the same message when there is no token at all', async () => {
    // A bookmarked callback URL is the same dead end as an expired link, and
    // two ways of saying so is one too many.
    render(<CallbackClient token={undefined} />);

    expect(await screen.findByRole('heading', { name: /cannot be used/i })).toBeInTheDocument();
  });

  it('shows the same message when the network fails', async () => {
    server.use(http.post(ENDPOINT, () => HttpResponse.error()));

    render(<CallbackClient token="tok-abc" />);

    expect(await screen.findByRole('heading', { name: /cannot be used/i })).toBeInTheDocument();
  });

  it('moves focus to the error heading', async () => {
    server.use(http.post(ENDPOINT, () => HttpResponse.json({}, { status: 401 })));

    render(<CallbackClient token="spent" />);

    // The user arrived from outside the app, so focus was nowhere useful and
    // the error is the only thing on the page.
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /cannot be used/i })).toHaveFocus(),
    );
  });

  it('offers a way back to requesting a link', async () => {
    server.use(http.post(ENDPOINT, () => HttpResponse.json({}, { status: 401 })));

    render(<CallbackClient token="spent" />);

    expect(await screen.findByRole('link', { name: /request a new link/i })).toBeInTheDocument();
  });
});
