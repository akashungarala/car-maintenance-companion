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
const VEHICLES = '/apps/car-maintenance-companion/api/vehicles';

/** The page fetches identity and vehicles together; most tests care about one. */
const signedIn = (vehicles: unknown[] = []) => [
  http.get(ME, () => HttpResponse.json({ id: 'u1', email: 'sam@example.com' })),
  http.get(VEHICLES, () => HttpResponse.json(vehicles)),
];

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
    server.use(...signedIn());

    render(<GarageClient />);

    expect(await screen.findByText(/sam@example.com/)).toBeInTheDocument();
  });

  it('shows nothing about the user while loading', () => {
    server.use(...signedIn());

    render(<GarageClient />);

    // A page that optimistically renders an address it has not confirmed will
    // show the wrong one to somebody eventually.
    expect(screen.queryByText(/sam@example.com/)).not.toBeInTheDocument();
  });

  it('goes to sign-in when the session is not valid', async () => {
    replace.mockClear();
    server.use(
      http.get(ME, () => HttpResponse.json({}, { status: 401 })),
      http.get(VEHICLES, () => HttpResponse.json([])),
    );

    render(<GarageClient />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/signin'));
  });

  it('offers a retry instead of redirecting when the server errors', async () => {
    replace.mockClear();
    server.use(
      http.get(ME, () => HttpResponse.json({}, { status: 500 })),
      http.get(VEHICLES, () => HttpResponse.json([])),
    );

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
      ...signedIn(),
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
      ...signedIn(),
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
    server.use(...signedIn([]));

    render(<GarageClient />);

    expect(await screen.findByRole('heading', { name: /add your first car/i })).toBeInTheDocument();
  });

  it('lists the vehicles it was given', async () => {
    server.use(
      ...signedIn([
        {
          id: 'v1',
          year: 2019,
          make: 'Honda',
          model: 'Civic',
          nickname: 'The Civic',
          display_name: 'The Civic',
          odometer: 48200,
          odometer_recorded_at: '2026-09-09T00:00:00Z',
          annual_mileage: 12000,
          created_at: '2026-09-09T00:00:00Z',
        },
      ]),
    );

    render(<GarageClient />);

    expect(await screen.findByRole('heading', { name: 'The Civic' })).toBeInTheDocument();
    expect(screen.getByText('48,200 miles')).toBeInTheDocument();
  });

  it('offers the add action in the header once a vehicle exists', async () => {
    server.use(
      ...signedIn([
        {
          id: 'v1',
          year: 2019,
          make: 'Honda',
          model: 'Civic',
          nickname: null,
          display_name: '2019 Honda Civic',
          odometer: 1,
          odometer_recorded_at: '2026-09-09T00:00:00Z',
          annual_mileage: 12000,
          created_at: '2026-09-09T00:00:00Z',
        },
      ]),
    );

    render(<GarageClient />);

    expect(await screen.findAllByRole('link', { name: /add a vehicle/i })).toHaveLength(1);
  });
});
