/**
 * The route entry points.
 *
 * Thin wrappers, but not free of failure modes: a wrong import path, a prop
 * renamed on the client component, or a page that forgets to pass the token
 * through all compile and then break at runtime. Rendering each one costs
 * almost nothing and catches exactly that.
 */
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '../mocks/node';
import CallbackPage from './auth/callback/page';
import AddVehiclePage from './garage/add/page';
import GaragePage from './garage/page';
import SignInPage from './signin/page';

const { router } = vi.hoisted(() => ({ router: { replace: vi.fn() } }));
vi.mock('next/navigation', () => ({ useRouter: () => router }));

describe('route entry points', () => {
  it('renders the sign-in page', () => {
    render(<SignInPage />);

    expect(screen.getByRole('heading', { name: /sign in to your garage/i })).toBeInTheDocument();
  });

  it('renders the garage page', () => {
    server.use(
      http.get('/apps/car-maintenance-companion/api/auth/me', () =>
        HttpResponse.json({ id: 'u1', email: 'sam@example.com' }),
      ),
      http.get('/apps/car-maintenance-companion/api/vehicles', () => HttpResponse.json([])),
    );

    render(<GaragePage />);

    expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument();
  });

  it('renders the add-vehicle page', () => {
    render(<AddVehiclePage />);

    expect(screen.getByRole('heading', { name: /add a vehicle/i })).toBeInTheDocument();
  });

  it('passes the token from the query string to the callback client', async () => {
    // The one piece of real behaviour in these wrappers: losing the token here
    // would make every sign-in link fail with "this link cannot be used", and
    // the client component's own tests would still pass.
    const seen: string[] = [];
    server.use(
      http.post('/apps/car-maintenance-companion/api/auth/session', async ({ request }) => {
        seen.push(((await request.json()) as { token: string }).token);
        return HttpResponse.json({ status: 'signed_in' });
      }),
    );

    render(await CallbackPage({ searchParams: Promise.resolve({ token: 'tok-from-url' }) }));

    await vi.waitFor(() => expect(seen).toEqual(['tok-from-url']));
  });
});
