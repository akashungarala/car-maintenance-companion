'use client';

import { useRouter } from 'next/navigation';
import { useRef, useState } from 'react';

import { apiUrl } from '../../../lib/api';

const MIN_YEAR = 1900;
const MAX_YEAR = 2100;

/**
 * Three plausible answers rather than a number.
 *
 * Almost nobody knows their annual mileage, and a required number nobody knows
 * is a wall. The figure is corrected later by the act of marking maintenance
 * done, which is the whole design of the projection mechanic — so a rough
 * answer now costs nothing and a blocked form costs the user.
 */
const DRIVING_LEVELS = [
  { id: 'low', label: 'Low', miles: 6000 },
  { id: 'average', label: 'Average', miles: 12000 },
  { id: 'high', label: 'High', miles: 18000 },
] as const;

type Errors = Partial<Record<'year' | 'make' | 'model' | 'odometer' | 'exact' | 'form', string>>;

// The order fields appear in, so focus lands on the first error rather than
// the first one the validator happened to notice.
const FIELD_ORDER = ['year', 'make', 'model', 'odometer', 'exact'] as const;

export function AddVehicleForm() {
  const router = useRouter();
  const [year, setYear] = useState('');
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [odometer, setOdometer] = useState('');
  const [level, setLevel] = useState<string>('average');
  const [exact, setExact] = useState('');
  const [useExact, setUseExact] = useState(false);
  const [nickname, setNickname] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [saving, setSaving] = useState(false);

  // Separate refs rather than an object of them: reading `refs.year` during
  // render is accessing a ref container mid-render, which the compiler rules
  // reject -- and they are right that a pattern which happens to work today is
  // not one to build a form on.
  const yearRef = useRef<HTMLInputElement>(null);
  const makeRef = useRef<HTMLInputElement>(null);
  const modelRef = useRef<HTMLInputElement>(null);
  const odometerRef = useRef<HTMLInputElement>(null);
  const exactRef = useRef<HTMLInputElement>(null);

  function validate(): Errors {
    const found: Errors = {};
    const yearNumber = Number(year);
    if (!year.trim() || !Number.isInteger(yearNumber)) {
      found.year = `Enter a year between ${MIN_YEAR} and ${MAX_YEAR}.`;
    } else if (yearNumber < MIN_YEAR || yearNumber > MAX_YEAR) {
      found.year = `Enter a year between ${MIN_YEAR} and ${MAX_YEAR}.`;
    }
    if (!make.trim()) found.make = 'Enter the make.';
    if (!model.trim()) found.model = 'Enter the model.';

    const miles = Number(odometer);
    if (!odometer.trim() || Number.isNaN(miles)) {
      found.odometer = 'Enter the current mileage.';
    } else if (miles < 0) {
      found.odometer = 'Mileage cannot be negative.';
    }

    if (useExact) {
      const annual = Number(exact);
      if (!exact.trim() || Number.isNaN(annual) || annual < 0) {
        found.exact = 'Enter how many miles you drive a year.';
      }
    }
    return found;
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const found = validate();
    setErrors(found);

    if (Object.keys(found).length > 0) {
      // Assembled in the handler, not during render.
      const byField: Record<(typeof FIELD_ORDER)[number], HTMLInputElement | null> = {
        year: yearRef.current,
        make: makeRef.current,
        model: modelRef.current,
        odometer: odometerRef.current,
        exact: exactRef.current,
      };
      const first = FIELD_ORDER.find((name) => found[name]);
      if (first) byField[first]?.focus();
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(apiUrl('/vehicles'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          year: Number(year),
          make: make.trim(),
          model: model.trim(),
          odometer: Number(odometer),
          annual_mileage: useExact
            ? Number(exact)
            : (DRIVING_LEVELS.find((l) => l.id === level)?.miles ?? 12000),
          ...(nickname.trim() ? { nickname: nickname.trim() } : {}),
        }),
      });

      if (response.status === 401) {
        router.replace('/signin');
        return;
      }
      if (!response.ok) {
        // Values are never cleared. Losing five fields to a server hiccup is
        // the fastest way to lose the user with them.
        setErrors({ form: 'Something went wrong saving your vehicle. Please try again.' });
        setSaving(false);
        return;
      }
      router.replace('/garage');
    } catch {
      setErrors({ form: 'Something went wrong saving your vehicle. Please try again.' });
      setSaving(false);
    }
  }

  return (
    <form
      noValidate
      onSubmit={submit}
      className="rounded-xl bg-white p-6 shadow-sm dark:bg-neutral-900"
    >
      <h1 className="text-lg font-semibold">Add a vehicle</h1>

      {errors.form ? (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800"
        >
          {errors.form}
        </div>
      ) : null}

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="year" className="block text-sm font-medium">
            Year
          </label>
          <>
            <input
              id="year"
              ref={yearRef}
              inputMode="numeric"
              placeholder="2019"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              aria-invalid={errors.year ? true : undefined}
              aria-describedby={errors.year ? 'year-error' : undefined}
              className={`mt-1 w-full rounded-lg border px-3 py-2.5 dark:bg-neutral-950 ${errors.year ? 'border-2 border-red-600' : 'border-neutral-300 dark:border-neutral-700'}`}
            />
            {errors.year ? (
              <p id="year-error" className="mt-1 text-xs font-medium text-red-700">
                {errors.year}
              </p>
            ) : null}
          </>
        </div>
        <div>
          <label htmlFor="make" className="block text-sm font-medium">
            Make
          </label>
          <>
            <input
              id="make"
              ref={makeRef}
              placeholder="Honda"
              value={make}
              onChange={(e) => setMake(e.target.value)}
              aria-invalid={errors.make ? true : undefined}
              aria-describedby={errors.make ? 'make-error' : undefined}
              className={`mt-1 w-full rounded-lg border px-3 py-2.5 dark:bg-neutral-950 ${errors.make ? 'border-2 border-red-600' : 'border-neutral-300 dark:border-neutral-700'}`}
            />
            {errors.make ? (
              <p id="make-error" className="mt-1 text-xs font-medium text-red-700">
                {errors.make}
              </p>
            ) : null}
          </>
        </div>
        <div>
          <label htmlFor="model" className="block text-sm font-medium">
            Model
          </label>
          <>
            <input
              id="model"
              ref={modelRef}
              placeholder="Civic"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              aria-invalid={errors.model ? true : undefined}
              aria-describedby={errors.model ? 'model-error' : undefined}
              className={`mt-1 w-full rounded-lg border px-3 py-2.5 dark:bg-neutral-950 ${errors.model ? 'border-2 border-red-600' : 'border-neutral-300 dark:border-neutral-700'}`}
            />
            {errors.model ? (
              <p id="model-error" className="mt-1 text-xs font-medium text-red-700">
                {errors.model}
              </p>
            ) : null}
          </>
        </div>
      </div>

      <div className="mt-4">
        <label htmlFor="odometer" className="block text-sm font-medium">
          Current mileage
        </label>
        <input
          id="odometer"
          ref={odometerRef}
          inputMode="numeric"
          placeholder="48200"
          value={odometer}
          onChange={(e) => setOdometer(e.target.value)}
          aria-invalid={errors.odometer ? true : undefined}
          aria-describedby={errors.odometer ? 'odometer-error' : undefined}
          className={`mt-1 w-full rounded-lg border px-3 py-2.5 dark:bg-neutral-950 ${errors.odometer ? 'border-2 border-red-600' : 'border-neutral-300 dark:border-neutral-700'}`}
        />
        {errors.odometer ? (
          <p id="odometer-error" className="mt-1 text-xs font-medium text-red-700">
            {errors.odometer}
          </p>
        ) : null}
      </div>

      {/* A fieldset with a legend, so a screen reader announces the question
          before the options rather than three unexplained buttons. */}
      <fieldset className="mt-5">
        <legend className="text-sm font-medium">How much do you drive?</legend>
        {!useExact ? (
          <>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {DRIVING_LEVELS.map((option) => (
                <label
                  key={option.id}
                  className={`cursor-pointer rounded-lg border p-3 ${level === option.id ? 'border-2 border-neutral-900 bg-neutral-50 dark:border-neutral-100 dark:bg-neutral-800' : 'border-neutral-300 dark:border-neutral-700'}`}
                >
                  <input
                    type="radio"
                    name="driving-level"
                    value={option.id}
                    checked={level === option.id}
                    onChange={() => setLevel(option.id)}
                    className="mr-2"
                  />
                  <span className="text-sm font-medium">{option.label}</span>
                  <span className="block text-xs text-neutral-500">
                    about {option.miles.toLocaleString('en-US')} mi/yr
                  </span>
                </label>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setUseExact(true)}
              className="mt-2 text-sm underline"
            >
              I know my exact mileage
            </button>
          </>
        ) : (
          <div className="mt-2">
            <label htmlFor="exact" className="block text-sm font-medium">
              Miles per year
            </label>
            <input
              id="exact"
              ref={exactRef}
              inputMode="numeric"
              placeholder="9000"
              value={exact}
              onChange={(e) => setExact(e.target.value)}
              aria-invalid={errors.exact ? true : undefined}
              aria-describedby={errors.exact ? 'exact-error' : undefined}
              className={`mt-1 w-full rounded-lg border px-3 py-2.5 dark:bg-neutral-950 ${errors.exact ? 'border-2 border-red-600' : 'border-neutral-300 dark:border-neutral-700'}`}
            />
            {errors.exact ? (
              <p id="exact-error" className="mt-1 text-xs font-medium text-red-700">
                {errors.exact}
              </p>
            ) : null}
            <button
              type="button"
              onClick={() => setUseExact(false)}
              className="mt-2 text-sm underline"
            >
              Choose from the options instead
            </button>
          </div>
        )}
      </fieldset>

      <div className="mt-5">
        <label htmlFor="nickname" className="block text-sm font-medium">
          Nickname <span className="font-normal text-neutral-500">(optional)</span>
        </label>
        <input
          id="nickname"
          placeholder={year && make && model ? `${year} ${make} ${model}` : '2019 Honda Civic'}
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
          className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2.5 dark:border-neutral-700 dark:bg-neutral-950"
        />
      </div>

      <button
        type="submit"
        disabled={saving}
        className="mt-5 w-full rounded-lg bg-neutral-900 px-4 py-3 font-medium text-white disabled:bg-neutral-400 dark:bg-neutral-100 dark:text-neutral-900"
      >
        {saving ? 'Adding…' : 'Add vehicle'}
      </button>
    </form>
  );
}
