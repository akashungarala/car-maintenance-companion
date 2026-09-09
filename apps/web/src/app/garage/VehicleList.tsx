import Link from 'next/link';

import { formatMiles, type Vehicle } from '../../lib/vehicles';

const ADD_HREF = '/apps/car-maintenance-companion/garage/add';

export function VehicleList({ vehicles }: { vehicles: Vehicle[] }) {
  if (vehicles.length === 0) {
    return (
      <div className="px-4 py-12 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-2xl dark:bg-neutral-800">
          🚗
        </div>
        {/* The most important screen in this story: a first-time user arrives
            here straight after signing in, and a blank page with a button is an
            instruction to guess. This states the exchange — two pieces of
            information, in return for the thing they came for. */}
        <h2 className="mt-3 text-base font-semibold">Add your first car</h2>
        <p className="mx-auto mt-1 max-w-sm text-sm text-neutral-600 dark:text-neutral-400">
          Tell us what you drive and roughly how much, and we will keep track of what it needs and
          when.
        </p>
        <Link
          href={ADD_HREF}
          className="mt-4 inline-block rounded-lg bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
        >
          Add a vehicle
        </Link>
      </div>
    );
  }

  return (
    // A real list, so a screen reader announces how many vehicles there are
    // before reading them out.
    <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
      {vehicles.map((vehicle) => (
        <li key={vehicle.id}>
          {/* The whole card is the target, not a "view" link tucked in a
              corner: on a phone the card is what the thumb aims at. */}
          <Link
            href={`${ADD_HREF.replace('/add', '')}/${vehicle.id}`}
            className="block px-4 py-4 hover:bg-neutral-50 dark:hover:bg-neutral-800"
          >
            <h2 className="text-base font-semibold">{vehicle.display_name}</h2>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              {vehicle.year} {vehicle.make} {vehicle.model}
            </p>
            <p className="mt-1 text-sm text-neutral-500">{formatMiles(vehicle.odometer)}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
