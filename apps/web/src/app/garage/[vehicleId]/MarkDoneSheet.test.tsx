/**
 * UX-007 acceptance criteria.
 *
 * See docs/ux/ux-007-mark-done.md.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '../../../mocks/node';
import { MarkDoneSheet } from './MarkDoneSheet';

const COMPLETE = '/apps/car-maintenance-companion/api/vehicles/v1/items/i1/complete';

const item = { id: 'i1', name: 'Engine oil & filter' };

function renderSheet(overrides: Record<string, unknown> = {}) {
  const onDone = vi.fn();
  const onClose = vi.fn();
  render(
    <MarkDoneSheet
      vehicleId="v1"
      item={item}
      estimatedMileage={48200}
      onDone={onDone}
      onClose={onClose}
      {...overrides}
    />,
  );
  return { onDone, onClose };
}

describe('MarkDoneSheet', () => {
  it('names the item it is recording', () => {
    renderSheet();

    expect(screen.getByRole('dialog', { name: /engine oil/i })).toBeInTheDocument();
  });

  it('prefills the odometer with the current estimate', () => {
    // A blank field asks everyone to walk outside; somebody who has not looked
    // at their dashboard can just accept this.
    renderSheet();

    expect(screen.getByLabelText(/odometer/i)).toHaveValue('48200');
  });

  it('asks for the odometer and nothing else', () => {
    // Every additional field is a reason to close the sheet.
    renderSheet();

    expect(screen.queryByLabelText(/cost|price|garage|note/i)).not.toBeInTheDocument();
  });

  it('names the previous reading when the number went backwards', async () => {
    const user = userEvent.setup();
    const seen = vi.fn();
    server.use(
      http.post(COMPLETE, () => {
        seen();
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderSheet();

    const field = screen.getByLabelText(/odometer/i);
    await user.clear(field);
    await user.type(field, '4820');
    await user.click(screen.getByRole('button', { name: /mark as done/i }));

    // 4820 for 48200 is the mistake this message exists for, so it shows the
    // number to compare against.
    expect(await screen.findByText(/48,200/)).toBeInTheDocument();
    expect(seen).not.toHaveBeenCalled();
  });

  it('records a valid reading and closes', async () => {
    const user = userEvent.setup();
    let sent: Record<string, unknown> = {};
    server.use(
      http.post(COMPLETE, async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: 'r1' }, { status: 201 });
      }),
    );
    const { onDone } = renderSheet();

    const field = screen.getByLabelText(/odometer/i);
    await user.clear(field);
    await user.type(field, '53000');
    await user.click(screen.getByRole('button', { name: /mark as done/i }));

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(sent['odometer']).toBe(53000);
    expect(sent['performed_at']).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('stays open with the values intact when saving fails', async () => {
    const user = userEvent.setup();
    server.use(http.post(COMPLETE, () => HttpResponse.json({}, { status: 500 })));
    const { onDone } = renderSheet();

    const field = screen.getByLabelText(/odometer/i);
    await user.clear(field);
    await user.type(field, '53000');
    await user.click(screen.getByRole('button', { name: /mark as done/i }));

    // Closing on failure would lose what they typed and leave them unsure
    // whether it saved.
    expect(await screen.findByText(/something went wrong/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/odometer/i)).toHaveValue('53000');
    expect(onDone).not.toHaveBeenCalled();
  });

  it('surfaces the reason when the server refuses the reading', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(COMPLETE, () =>
        HttpResponse.json(
          { detail: 'The new reading is lower than the previous one.' },
          { status: 422 },
        ),
      ),
    );
    renderSheet({ estimatedMileage: 10 });

    await user.click(screen.getByRole('button', { name: /mark as done/i }));

    expect(await screen.findByText(/lower than the previous one/i)).toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    const { onClose } = renderSheet();

    await user.keyboard('{Escape}');

    expect(onClose).toHaveBeenCalled();
  });
});
