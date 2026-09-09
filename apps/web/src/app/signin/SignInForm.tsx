'use client';

import { useRef, useState } from 'react';

import { apiUrl } from '../../lib/api';

type Status =
  | { kind: 'editing'; error?: string }
  | { kind: 'sending' }
  | { kind: 'sent'; email: string }
  | { kind: 'failed'; message: string }
  | { kind: 'limited'; seconds: number };

/**
 * Shape only. Confirming an address exists is impossible without sending to
 * it, which is the whole flow — so this rejects obvious nonsense and nothing
 * more. The server validates independently; this exists to avoid a round trip
 * and to put the message next to the field.
 */
const PLAUSIBLE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function SignInForm() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<Status>({ kind: 'editing' });
  const confirmationHeading = useRef<HTMLHeadingElement>(null);

  const busy = status.kind === 'sending';

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = email.trim();

    // Validation runs on submit, never on keystroke: telling someone their
    // address is malformed while they are still typing it tells them they are
    // wrong before they have finished being right.
    if (!trimmed) {
      setStatus({ kind: 'editing', error: 'Enter your email address.' });
      return;
    }
    if (!PLAUSIBLE_EMAIL.test(trimmed)) {
      setStatus({ kind: 'editing', error: 'That does not look like an email address.' });
      return;
    }

    setStatus({ kind: 'sending' });
    try {
      const response = await fetch(apiUrl('/auth/magic-link'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: trimmed }),
      });

      if (response.status === 429) {
        const retry = Number(response.headers.get('Retry-After') ?? '60');
        setStatus({ kind: 'limited', seconds: Number.isFinite(retry) ? retry : 60 });
        return;
      }
      if (!response.ok) {
        setStatus({ kind: 'failed', message: 'Something went wrong sending your link.' });
        return;
      }

      setStatus({ kind: 'sent', email: trimmed });
      // Focus follows the content. Without this a screen-reader user is left
      // on a button that no longer exists, with nothing announcing what
      // replaced it.
      requestAnimationFrame(() => confirmationHeading.current?.focus());
    } catch {
      setStatus({
        kind: 'failed',
        message: navigator.onLine
          ? 'Something went wrong sending your link.'
          : 'You appear to be offline.',
      });
    }
  }

  if (status.kind === 'sent') {
    return (
      <div aria-live="polite" className="rounded-xl bg-white p-6 shadow-sm dark:bg-neutral-900">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-xl dark:bg-emerald-900">
          ✉️
        </div>
        <h1
          ref={confirmationHeading}
          tabIndex={-1}
          className="mt-3 text-lg font-semibold outline-none"
        >
          Check your email
        </h1>
        <p className="mt-1.5 text-sm text-neutral-600 dark:text-neutral-400">
          We sent a link to{' '}
          <strong className="text-neutral-900 dark:text-neutral-100">{status.email}</strong>. It
          works once and expires in 15 minutes.
        </p>
        <p className="mt-4 text-sm text-neutral-600 dark:text-neutral-400">
          Wrong address?{' '}
          <button
            type="button"
            className="font-medium text-neutral-900 underline dark:text-neutral-100"
            onClick={() => {
              setEmail('');
              setStatus({ kind: 'editing' });
            }}
          >
            Use a different one
          </button>
        </p>
      </div>
    );
  }

  const validationError = status.kind === 'editing' ? status.error : undefined;
  const banner =
    status.kind === 'failed'
      ? status.message
      : status.kind === 'limited'
        ? `Too many attempts. Try again in ${status.seconds} seconds.`
        : undefined;

  return (
    <form
      noValidate
      onSubmit={submit}
      className="rounded-xl bg-white p-6 shadow-sm dark:bg-neutral-900"
    >
      <h1 className="text-lg font-semibold">Sign in to your garage</h1>
      <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
        We will email you a link. No password needed.
      </p>

      {banner ? (
        <div
          role="alert"
          className={`mt-4 rounded-lg border px-3 py-2.5 text-sm ${
            status.kind === 'limited'
              ? 'border-amber-200 bg-amber-50 text-amber-900'
              : 'border-red-200 bg-red-50 text-red-800'
          }`}
        >
          {banner}
        </div>
      ) : null}

      <label htmlFor="email" className="mt-5 block text-sm font-medium">
        Email address
      </label>
      <input
        id="email"
        name="email"
        type="email"
        autoComplete="email"
        inputMode="email"
        value={email}
        disabled={busy}
        aria-invalid={validationError ? true : undefined}
        aria-describedby={validationError ? 'email-error' : undefined}
        onChange={(event) => setEmail(event.target.value)}
        className={`mt-1 w-full rounded-lg border px-3 py-2.5 dark:bg-neutral-950 ${
          validationError ? 'border-2 border-red-600' : 'border-neutral-300 dark:border-neutral-700'
        }`}
      />
      {validationError ? (
        <p id="email-error" role="alert" className="mt-1.5 text-sm font-medium text-red-700">
          {validationError}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-neutral-900 px-4 py-3 font-medium text-white disabled:bg-neutral-400 dark:bg-neutral-100 dark:text-neutral-900"
      >
        {busy ? (
          <>
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            Sending…
          </>
        ) : (
          'Email me a link'
        )}
      </button>
    </form>
  );
}
