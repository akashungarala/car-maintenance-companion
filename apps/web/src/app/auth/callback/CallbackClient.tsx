'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { apiUrl } from '../../../lib/api';

/**
 * Exchanges the sign-in link for a session.
 *
 * The exchange runs on mount rather than behind a button. Mail scanners
 * prefetch URLs with GET, so a GET that consumed the token would let a scanner
 * spend it before the user clicked — which presents as "this link has expired"
 * seconds after it arrived. A POST is not prefetched, so no click is needed to
 * defend against it.
 */
export function CallbackClient({ token }: { token: string | undefined }) {
  const router = useRouter();
  // Derived, not set in an effect: with no token the outcome is known at
  // render time, and an effect would mean one frame of "Signing you in…" for a
  // link that was never going to work.
  const [failed, setFailed] = useState(!token);
  const errorHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(apiUrl('/auth/session'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        if (cancelled) return;
        if (response.ok) {
          router.replace('/');
          return;
        }
        setFailed(true);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, router]);

  useEffect(() => {
    if (failed) errorHeading.current?.focus();
  }, [failed]);

  if (failed) {
    return (
      <div className="rounded-xl bg-white p-6 shadow-sm dark:bg-neutral-900">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-xl dark:bg-red-900">
          ⚠️
        </div>
        {/* One message for expired, already used, never existed and altered.
            Naming which would tell an attacker which tokens once existed, and
            none of the four changes what the user does next. */}
        <h1 ref={errorHeading} tabIndex={-1} className="mt-3 text-lg font-semibold outline-none">
          This link cannot be used
        </h1>
        <p className="mt-1.5 text-sm text-neutral-600 dark:text-neutral-400">
          Sign-in links work once and expire after 15 minutes.
        </p>
        <a
          href="/apps/car-maintenance-companion/signin"
          className="mt-4 inline-block rounded-lg bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
        >
          Request a new link
        </a>
      </div>
    );
  }

  return (
    <div aria-live="polite" className="rounded-xl bg-white p-6 shadow-sm dark:bg-neutral-900">
      <div className="flex items-center gap-3">
        {/* motion-reduce: a spinner is decoration, and for some people it is
            actively unpleasant. The text carries the meaning. */}
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none" />
        <p className="text-base font-medium">Signing you in…</p>
      </div>
    </div>
  );
}
