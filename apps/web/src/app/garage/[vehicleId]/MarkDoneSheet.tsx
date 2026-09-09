'use client';

import { useEffect, useRef, useState } from 'react';

import { apiUrl } from '../../../lib/api';

type Props = {
  vehicleId: string;
  item: { id: string; name: string };
  estimatedMileage: number;
  onDone: () => void;
  onClose: () => void;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * One question, asked over the dashboard rather than on a page of its own.
 *
 * The context — which car, which item — is what makes a single input legible,
 * and a full-page form would throw it away.
 */
export function MarkDoneSheet({ vehicleId, item, estimatedMileage, onDone, onClose }: Props) {
  // Prefilled with our estimate. A blank field asks everybody to walk outside;
  // somebody who has not checked can simply accept it, and somebody who has can
  // correct it in two taps.
  const [odometer, setOdometer] = useState(String(estimatedMileage));
  const [performedAt, setPerformedAt] = useState(today);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const odometerRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    odometerRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  async function save() {
    const reading = Number(odometer);
    if (!odometer.trim() || Number.isNaN(reading) || reading < 0) {
      setError('Enter the current odometer reading.');
      return;
    }
    if (reading < estimatedMileage) {
      // Caught here as well as by the API, so the common typo never costs a
      // round trip — and the message names the number to compare against.
      setError(
        `That is lower than the last reading (${estimatedMileage.toLocaleString('en-US')} miles). ` +
          'Check the number — odometers do not go backwards.',
      );
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const response = await fetch(apiUrl(`/vehicles/${vehicleId}/items/${item.id}/complete`), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ odometer: reading, performed_at: performedAt }),
      });

      if (response.ok) {
        onDone();
        return;
      }
      if (response.status === 422) {
        // The API's own reason, which is more specific than anything the
        // client could infer.
        const body = (await response.json().catch(() => ({}))) as { detail?: string };
        setError(body.detail ?? 'That reading does not look right.');
        setSaving(false);
        return;
      }
      setError('Something went wrong saving this. Please try again.');
      setSaving(false);
    } catch {
      setError('Something went wrong saving this. Please try again.');
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-10 flex items-end justify-center bg-black/40 sm:items-center">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={item.name}
        className="w-full rounded-t-xl bg-white p-6 shadow-lg sm:max-w-[420px] sm:rounded-xl dark:bg-neutral-900"
      >
        <h2 className="text-lg font-semibold">{item.name}</h2>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          Recording this as done updates what we expect next.
        </p>

        {error ? (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800"
          >
            {error}
          </div>
        ) : null}

        <label htmlFor="done-odometer" className="mt-4 block text-sm font-medium">
          Odometer
        </label>
        <input
          id="done-odometer"
          ref={odometerRef}
          inputMode="numeric"
          value={odometer}
          onChange={(e) => setOdometer(e.target.value)}
          aria-describedby={error ? 'done-error' : undefined}
          className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2.5 dark:border-neutral-700 dark:bg-neutral-950"
        />

        <label htmlFor="done-date" className="mt-4 block text-sm font-medium">
          When
        </label>
        <input
          id="done-date"
          type="date"
          value={performedAt}
          onChange={(e) => setPerformedAt(e.target.value)}
          className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2.5 dark:border-neutral-700 dark:bg-neutral-950"
        />

        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-lg border border-neutral-300 px-4 py-3 font-medium dark:border-neutral-700"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={saving}
            className="flex-1 rounded-lg bg-neutral-900 px-4 py-3 font-medium text-white disabled:bg-neutral-400 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {saving ? 'Saving…' : 'Mark as done'}
          </button>
        </div>
      </div>
    </div>
  );
}
