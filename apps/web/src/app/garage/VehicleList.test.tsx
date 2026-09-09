/**
 * UX-005 acceptance criteria for the list itself.
 *
 * See docs/ux/ux-005-vehicle-list.md.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Vehicle } from '../../lib/vehicles';
import { VehicleList } from './VehicleList';

const civic: Vehicle = {
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
};

const outback: Vehicle = {
  ...civic,
  id: 'v2',
  year: 2014,
  make: 'Subaru',
  model: 'Outback',
  nickname: null,
  display_name: '2014 Subaru Outback',
  odometer: 122650,
};

describe('VehicleList', () => {
  it('explains what to do when there are no vehicles', () => {
    // A first-time user arrives here immediately after signing in, and a blank
    // page with a button is an instruction to guess.
    render(<VehicleList vehicles={[]} />);

    expect(screen.getByRole('heading', { name: /add your first car/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /add a vehicle/i })).toBeInTheDocument();
  });

  it('shows each vehicle with its name, identity and mileage', () => {
    render(<VehicleList vehicles={[civic]} />);

    expect(screen.getByRole('heading', { name: 'The Civic' })).toBeInTheDocument();
    expect(screen.getByText('2019 Honda Civic')).toBeInTheDocument();
    expect(screen.getByText('48,200 miles')).toBeInTheDocument();
  });

  it('falls back to year, make and model when unnamed', () => {
    // No card is ever untitled.
    render(<VehicleList vehicles={[outback]} />);

    expect(screen.getByRole('heading', { name: '2014 Subaru Outback' })).toBeInTheDocument();
  });

  it('renders the vehicles as a list so their number is announced', () => {
    render(<VehicleList vehicles={[civic, outback]} />);

    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  it('keeps the order it was given', () => {
    // Newest first is the API's job; re-sorting here would mean two places
    // decide the order and one of them would eventually be wrong.
    render(<VehicleList vehicles={[civic, outback]} />);

    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(['The Civic', '2014 Subaru Outback']);
  });
  it('links each vehicle to its dashboard', () => {
    render(<VehicleList vehicles={[civic]} />);

    // The whole card is the target: on a phone that is what the thumb aims at.
    expect(screen.getByRole('link', { name: /the civic/i })).toHaveAttribute(
      'href',
      '/apps/car-maintenance-companion/garage/v1',
    );
  });
});
