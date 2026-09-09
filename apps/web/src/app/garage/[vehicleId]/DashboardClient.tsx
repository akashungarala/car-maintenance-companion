'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { apiUrl } from '../../../lib/api';
import { BANDS, formatDueDate, type Plan, type PlanItem, type PlanStatus } from '../../../lib/plan';

type State = { kind: 'loading' } | { kind: 'ready'; plan: Plan } | { kind: 'error' };

const BAND_STYLES: Record<PlanStatus, string> = {
  // Colour reinforces the heading; the word carries the meaning. Somebody who
  // cannot distinguish these still reads "Overdue".
  overdue: 'bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200',
  due_soon: 'bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  upcoming: 'bg-neutral-50 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300',
};

function Item({ item }: { item: PlanItem }) {
  return (
    <li className="px-5 py-4">
      <div className="sm:flex sm:items-baseline sm:justify-between sm:gap-4">
        <p className="font-medium">{item.name}</p>
        <p className="text-sm text-neutral-600 dark:text-neutral-400">
          {item.due_at ? (
            <>
              due {formatDueDate(item.due_at)}
              {item.due_mileage !== null
                ? ` · at ${item.due_mileage.toLocaleString('en-US')} mi`
                : null}
            </>
          ) : (
            'not scheduled'
          )}
        </p>
      </div>
      {item.is_assumed ? (
        // The single most important detail on this screen. Real text, not an
        // icon or a tooltip: touch devices have no hover, and what this says is
        // too important to hide behind one.
        <p className="mt-1 text-xs text-neutral-500">
          Assumed: we started tracking this when you added the car.
        </p>
      ) : null}
    </li>
  );
}

export function DashboardClient({ vehicleId }: { vehicleId: string }) {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const response = await fetch(apiUrl(`/vehicles/${vehicleId}/plan`), {
          credentials: 'same-origin',
        });
        if (cancelled) return;

        if (response.status === 401) {
          router.replace('/signin');
          return;
        }
        if (response.status === 404) {
          // Gone, or never theirs. Either way the garage is where they belong.
          router.replace('/garage');
          return;
        }
        if (!response.ok) {
          setState({ kind: 'error' });
          return;
        }
        const plan = (await response.json()) as Plan;
        if (!cancelled) setState({ kind: 'ready', plan });
      } catch {
        if (!cancelled) setState({ kind: 'error' });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [vehicleId, attempt, router]);

  if (state.kind === 'error') {
    return (
      <div className="rounded-xl bg-white p-6 text-center shadow-sm dark:bg-neutral-900">
        <h2 className="text-base font-semibold">Could not load this vehicle</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          Something went wrong on our side.
        </p>
        <button
          type="button"
          onClick={() => {
            setState({ kind: 'loading' });
            setAttempt((n) => n + 1);
          }}
          className="mt-4 rounded-lg bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
        >
          Try again
        </button>
      </div>
    );
  }

  if (state.kind === 'loading') {
    return (
      <div
        aria-busy="true"
        className="overflow-hidden rounded-xl bg-white shadow-sm dark:bg-neutral-900"
      >
        {[0, 1, 2].map((row) => (
          <div key={row} aria-hidden="true" className="space-y-2 px-5 py-4">
            <div className="h-4 w-40 animate-pulse rounded bg-neutral-200 motion-reduce:animate-none dark:bg-neutral-700" />
            <div className="h-3 w-52 animate-pulse rounded bg-neutral-100 motion-reduce:animate-none dark:bg-neutral-800" />
          </div>
        ))}
      </div>
    );
  }

  const { plan } = state;

  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-sm dark:bg-neutral-900">
      <div className="border-b border-neutral-200 px-5 py-4 dark:border-neutral-800">
        <p className="text-sm text-neutral-500">
          <strong className="text-neutral-900 dark:text-neutral-100">
            {plan.estimated_mileage.toLocaleString('en-US')} miles
          </strong>{' '}
          estimated today
        </p>
      </div>

      {BANDS.map(({ status, label }) => {
        const items = plan.items.filter((item) => item.status === status);
        // Bands with nothing in them are not rendered: an "Overdue · 0"
        // heading is reassurance, and a section heading is not for that.
        if (items.length === 0) return null;

        return (
          <section key={status} className="border-b border-neutral-200 dark:border-neutral-800">
            <h2 className={`px-5 py-2 text-sm font-semibold ${BAND_STYLES[status]}`}>
              {label} · {items.length}
            </h2>
            <ul className="divide-y divide-neutral-100 dark:divide-neutral-800">
              {items.map((item) => (
                <Item key={item.id} item={item} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
