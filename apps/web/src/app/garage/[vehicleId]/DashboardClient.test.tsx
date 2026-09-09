/**
 * UX-006 acceptance criteria.
 *
 * See docs/ux/ux-006-dashboard.md.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '../../../mocks/node';
import { DashboardClient } from './DashboardClient';

const PLAN = '/apps/car-maintenance-companion/api/vehicles/v1/plan';

const { replace, router } = vi.hoisted(() => {
  const replaceFn = vi.fn();
  return { replace: replaceFn, router: { replace: replaceFn } };
});
vi.mock('next/navigation', () => ({ useRouter: () => router }));

const item = (over: Record<string, unknown> = {}) => ({
  id: 'i1',
  name: 'Engine oil & filter',
  due_at: '2027-02-08',
  due_mileage: 53200,
  status: 'due_soon',
  is_assumed: true,
  ...over,
});

const plan = (items: unknown[]) =>
  http.get(PLAN, () => HttpResponse.json({ vehicle_id: 'v1', estimated_mileage: 48200, items }));

describe('DashboardClient', () => {
  it('shows the estimated mileage, labelled as an estimate', async () => {
    server.use(plan([item()]));

    render(<DashboardClient vehicleId="v1" />);

    expect(await screen.findByText(/48,200 miles/)).toBeInTheDocument();
    expect(screen.getByText(/estimated/i)).toBeInTheDocument();
  });

  it('groups items under their band', async () => {
    server.use(
      plan([
        item({ id: 'a', name: 'Wash & interior clean', status: 'overdue' }),
        item({ id: 'b', status: 'due_soon' }),
        item({ id: 'c', name: 'Coolant', status: 'upcoming' }),
      ]),
    );

    render(<DashboardClient vehicleId="v1" />);

    expect(await screen.findByRole('heading', { name: /overdue/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /due soon/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /upcoming/i })).toBeInTheDocument();
  });

  it('does not render a band with nothing in it', async () => {
    // An "Overdue · 0" heading is reassurance, and a section heading is not for
    // reassurance.
    server.use(plan([item({ status: 'upcoming' })]));

    render(<DashboardClient vehicleId="v1" />);

    await screen.findByRole('heading', { name: /upcoming/i });
    expect(screen.queryByRole('heading', { name: /overdue/i })).not.toBeInTheDocument();
  });

  it('says in words when a date is assumed', async () => {
    // The single most important detail on the screen.
    server.use(plan([item({ is_assumed: true })]));

    render(<DashboardClient vehicleId="v1" />);

    expect(await screen.findByText(/assumed/i)).toBeInTheDocument();
  });

  it('says nothing about assumptions once an item is known', async () => {
    server.use(plan([item({ is_assumed: false })]));

    render(<DashboardClient vehicleId="v1" />);

    await screen.findByText(/engine oil/i);
    expect(screen.queryByText(/assumed/i)).not.toBeInTheDocument();
  });

  it('writes dates out rather than in digits', async () => {
    server.use(plan([item({ due_at: '2027-02-08' })]));

    render(<DashboardClient vehicleId="v1" />);

    // 08/02/27 is two different days depending on the reader.
    expect(await screen.findByText(/8 February 2027/)).toBeInTheDocument();
  });

  it('reads "not scheduled" when an item has no due date', async () => {
    // A car that is not driven never needs its tires rotated; inventing a date
    // would be worse than saying so.
    server.use(plan([item({ name: 'Tire rotation', due_at: null, due_mileage: null })]));

    render(<DashboardClient vehicleId="v1" />);

    expect(await screen.findByText(/not scheduled/i)).toBeInTheDocument();
  });

  it('renders no dates while loading', () => {
    server.use(plan([item()]));

    render(<DashboardClient vehicleId="v1" />);

    expect(screen.queryByText(/2027/)).not.toBeInTheDocument();
  });

  it('goes to sign-in when the session has ended', async () => {
    replace.mockClear();
    server.use(http.get(PLAN, () => HttpResponse.json({}, { status: 401 })));

    render(<DashboardClient vehicleId="v1" />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/signin'));
  });

  it('offers a retry rather than redirecting when the server errors', async () => {
    replace.mockClear();
    server.use(http.get(PLAN, () => HttpResponse.json({}, { status: 500 })));

    render(<DashboardClient vehicleId="v1" />);

    expect(await screen.findByRole('button', { name: /try again/i })).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('returns to the garage when the vehicle is not found', async () => {
    replace.mockClear();
    server.use(http.get(PLAN, () => HttpResponse.json({}, { status: 404 })));

    render(<DashboardClient vehicleId="v1" />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/garage'));
  });
});
