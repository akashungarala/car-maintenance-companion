/**
 * UX-003 acceptance criteria.
 *
 * See docs/ux/ux-003-garage-and-sign-out.md.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '../../mocks/node';
import { GarageClient } from './GarageClient';

const ME = '/apps/car-maintenance-companion/api/auth/me';
const SESSION = '/apps/car-maintenance-companion/api/auth/session';

// vi.hoisted, because vi.mock is lifted above the imports and its factory
// cannot reach a const declared below it.
//
// The router object is created once, not per render. Real useRouter is stable;
// returning a fresh object each time changes the identity of everything that
// depends on it, which re-runs effects forever — a mistake that presents as
// the test runner exhausting its heap rather than as a failing assertion.
const { replace, router } = vi.hoisted(() => {
  const replaceFn = vi.fn();
  return { replace: replaceFn, router: { replace: replaceFn } };
});
vi.mock('next/navigation', () => ({ useRouter: () => router }));

describe('GarageClient', () => {
  it('shows the address once the API confirms it', async () => {
    server.use(http.get(ME, () => HttpResponse.json({ id: 'u1', email: 'sam@example.com' })));

    render(<GarageClient />);

    expect(await screen.findByText(/sam@example.com/)).toBeInTheDocument();
  });

  it('shows nothing about the user while loading', () => {
    server.use(http.get(ME, () => HttpResponse.json({ id: 'u1', email: 'sam@example.com' })));

    render(<GarageClient />);

    // A page that optimistically renders an address it has not confirmed will
    // show the wrong one to somebody eventually.
    expect(screen.queryByText(/sam@example.com/)).not.toBeInTheDocument();
  });

  it('goes to sign-in when the session is not valid', async () => {
    replace.mockClear();
    server.use(http.get(ME, () => HttpResponse.json({}, { status: 401 })));

    render(<GarageClient />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/signin'));
  });

  it('offers a retry instead of redirecting when the server errors', async () => {
    replace.mockClear();
    server.use(http.get(ME, () => HttpResponse.json({}, { status: 500 })));

    render(<GarageClient />);

    // Bouncing someone to sign-in because the server had a bad moment means
    // they sign in, land back here, and are bounced again.
    expect(await screen.findByRole('button', { name: /try again/i })).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('signs out by asking the server to revoke the session', async () => {
    const user = userEvent.setup();
    const methods: string[] = [];
    server.use(
      http.get(ME, () => HttpResponse.json({ id: 'u1', email: 'sam@example.com' })),
      http.delete(SESSION, ({ request }) => {
        methods.push(request.method);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    render(<GarageClient />);
    await screen.findByText(/sam@example.com/);

    await user.click(screen.getByRole('button', { name: /sign out/i }));

    await waitFor(() => expect(methods).toEqual(['DELETE']));
  });

  it('still leaves when signing out fails', async () => {
    const user = userEvent.setup();
    replace.mockClear();
    server.use(
      http.get(ME, () => HttpResponse.json({ id: 'u1', email: 'sam@example.com' })),
      http.delete(SESSION, () => HttpResponse.error()),
    );
    render(<GarageClient />);
    await screen.findByText(/sam@example.com/);

    await user.click(screen.getByRole('button', { name: /sign out/i }));

    // Leaving someone apparently signed in on a shared machine because the
    // network hiccuped is the worse of the two failures.
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/signin'));
  });

  it('names what is missing rather than showing a blank page', async () => {
    server.use(http.get(ME, () => HttpResponse.json({ id: 'u1', email: 'sam@example.com' })));

    render(<GarageClient />);

    expect(await screen.findByText(/your garage is empty/i)).toBeInTheDocument();
  });
});
