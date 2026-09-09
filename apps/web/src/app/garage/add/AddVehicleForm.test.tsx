/**
 * UX-004 acceptance criteria.
 *
 * See docs/ux/ux-004-add-vehicle.md.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '../../../mocks/node';
import { AddVehicleForm } from './AddVehicleForm';

const VEHICLES = '/apps/car-maintenance-companion/api/vehicles';

const { replace, router } = vi.hoisted(() => {
  const replaceFn = vi.fn();
  return { replace: replaceFn, router: { replace: replaceFn } };
});
vi.mock('next/navigation', () => ({ useRouter: () => router }));

async function fillValid(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^year/i), '2019');
  await user.type(screen.getByLabelText(/^make/i), 'Honda');
  await user.type(screen.getByLabelText(/^model/i), 'Civic');
  await user.type(screen.getByLabelText(/current mileage/i), '48200');
}

describe('AddVehicleForm', () => {
  it('labels every field', () => {
    render(<AddVehicleForm />);

    for (const label of [/^year/i, /^make/i, /^model/i, /current mileage/i, /nickname/i]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
  });

  it('preselects Average so the driving question can be skipped', async () => {
    const user = userEvent.setup();
    let sent: Record<string, unknown> = {};
    server.use(
      http.post(VEHICLES, async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 'v1' }, { status: 201 });
      }),
    );
    render(<AddVehicleForm />);

    await fillValid(user);
    await user.click(screen.getByRole('button', { name: /add vehicle/i }));

    // Almost nobody knows their annual mileage; a required number nobody knows
    // is a wall.
    await waitFor(() => expect(sent['annual_mileage']).toBe(12000));
  });

  it('reports each empty required field separately', async () => {
    const user = userEvent.setup();
    const seen = vi.fn();
    server.use(
      http.post(VEHICLES, () => {
        seen();
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    render(<AddVehicleForm />);

    await user.click(screen.getByRole('button', { name: /add vehicle/i }));

    expect(await screen.findByText(/enter a year/i)).toBeInTheDocument();
    expect(screen.getByText(/enter the make/i)).toBeInTheDocument();
    expect(screen.getByText(/enter the model/i)).toBeInTheDocument();
    expect(screen.getByText(/enter the current mileage/i)).toBeInTheDocument();
    expect(seen).not.toHaveBeenCalled();
  });

  it('rejects an impossible year', async () => {
    const user = userEvent.setup();
    render(<AddVehicleForm />);

    await user.type(screen.getByLabelText(/^year/i), '219');
    await user.click(screen.getByRole('button', { name: /add vehicle/i }));

    expect(await screen.findByText(/between 1900 and/i)).toBeInTheDocument();
  });

  it('rejects negative mileage', async () => {
    const user = userEvent.setup();
    render(<AddVehicleForm />);

    await user.type(screen.getByLabelText(/current mileage/i), '-5');
    await user.click(screen.getByRole('button', { name: /add vehicle/i }));

    expect(await screen.findByText(/cannot be negative/i)).toBeInTheDocument();
  });

  it('moves focus to the first field with an error', async () => {
    const user = userEvent.setup();
    render(<AddVehicleForm />);

    await user.click(screen.getByRole('button', { name: /add vehicle/i }));

    // Otherwise a keyboard user is left at the bottom of the form with
    // messages they cannot see.
    await waitFor(() => expect(screen.getByLabelText(/^year/i)).toHaveFocus());
  });

  it('accepts an exact annual mileage when asked for one', async () => {
    const user = userEvent.setup();
    let sent: Record<string, unknown> = {};
    server.use(
      http.post(VEHICLES, async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 'v1' }, { status: 201 });
      }),
    );
    render(<AddVehicleForm />);

    await fillValid(user);
    await user.click(screen.getByRole('button', { name: /exact mileage/i }));
    await user.type(screen.getByLabelText(/miles.*year/i), '9000');
    await user.click(screen.getByRole('button', { name: /add vehicle/i }));

    await waitFor(() => expect(sent['annual_mileage']).toBe(9000));
  });

  it('returns to the garage after a successful add', async () => {
    const user = userEvent.setup();
    replace.mockClear();
    server.use(http.post(VEHICLES, () => HttpResponse.json({ id: 'v1' }, { status: 201 })));
    render(<AddVehicleForm />);

    await fillValid(user);
    await user.click(screen.getByRole('button', { name: /add vehicle/i }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/garage'));
  });

  it('keeps every value when the server fails', async () => {
    const user = userEvent.setup();
    server.use(http.post(VEHICLES, () => HttpResponse.json({}, { status: 500 })));
    render(<AddVehicleForm />);

    await fillValid(user);
    await user.click(screen.getByRole('button', { name: /add vehicle/i }));

    // Losing five fields to a server hiccup is the fastest way to lose the
    // user with them.
    expect(await screen.findByText(/something went wrong/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^make/i)).toHaveValue('Honda');
    expect(screen.getByLabelText(/current mileage/i)).toHaveValue('48200');
  });

  it('sends the user to sign in if the session ended', async () => {
    const user = userEvent.setup();
    replace.mockClear();
    server.use(http.post(VEHICLES, () => HttpResponse.json({}, { status: 401 })));
    render(<AddVehicleForm />);

    await fillValid(user);
    await user.click(screen.getByRole('button', { name: /add vehicle/i }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/signin'));
  });
});
