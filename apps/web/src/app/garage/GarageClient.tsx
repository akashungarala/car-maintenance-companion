'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { apiUrl } from '../../lib/api';

type State =
  | { kind: 'loading' }
  | { kind: 'signed-in'; email: string }
  | { kind: 'error' }
  | { kind: 'leaving' };

/**
 * The first screen behind authentication.
 *
 * The redirect here is convenience, not security. The API refuses
 * unauthenticated requests on its own and would do so if this page were served
 * to the whole internet — this only avoids showing someone a shell they cannot
 * use. Treating a client-side redirect as a security control is how data ends
 * up in a payload that "only signed-in users can see".
 */
export function GarageClient() {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: 'loading' });

  // Bumped by the retry button to re-run the effect. The alternative -- a
  // useCallback the effect calls -- reads as setState-inside-an-effect to the
  // linter, and it is not wrong to be suspicious: the difference between safe
  // and cascading here is only that the writes happen after an await.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const response = await fetch(apiUrl('/auth/me'), { credentials: 'same-origin' });
        if (cancelled) return;

        if (response.status === 401) {
          router.replace('/signin');
          return;
        }
        if (!response.ok) {
          // Only a 401 means "not signed in". Anything else is the server
          // having a bad moment, and bouncing to sign-in would loop the user.
          setState({ kind: 'error' });
          return;
        }

        const body = (await response.json()) as { email: string };
        if (!cancelled) setState({ kind: 'signed-in', email: body.email });
      } catch {
        if (!cancelled) setState({ kind: 'error' });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [attempt, router]);

  async function signOut() {
    setState({ kind: 'leaving' });
    try {
      await fetch(apiUrl('/auth/session'), { method: 'DELETE', credentials: 'same-origin' });
    } catch {
      // Deliberately ignored. Leaving someone apparently signed in on a shared
      // machine because the network hiccuped is the worse of the two failures,
      // and the session still expires on its own.
    }
    router.replace('/signin');
  }

  if (state.kind === 'error') {
    return (
      <div className="rounded-xl bg-white p-6 text-center shadow-sm dark:bg-neutral-900">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-2xl dark:bg-amber-900">
          ⚠️
        </div>
        <h2 className="mt-3 text-base font-semibold">Could not load your garage</h2>
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

  const loading = state.kind === 'loading';

  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-sm dark:bg-neutral-900">
      <div
        aria-busy={loading}
        className="flex items-center justify-between gap-3 border-b border-neutral-200 px-4 py-3 dark:border-neutral-800"
      >
        {loading ? (
          // A skeleton, not a full-page spinner: the page's structure is known
          // before the answer is, and replacing everything makes the screen
          // flash on every visit.
          <div
            aria-hidden="true"
            className="h-4 w-40 animate-pulse rounded bg-neutral-200 motion-reduce:animate-none dark:bg-neutral-700"
          />
        ) : (
          <p aria-live="polite" className="truncate text-sm">
            Signed in as <strong>{state.kind === 'signed-in' ? state.email : ''}</strong>
          </p>
        )}
        <button
          type="button"
          onClick={() => void signOut()}
          disabled={state.kind === 'leaving'}
          className="shrink-0 rounded-lg border border-neutral-300 px-3 py-2 text-sm font-medium disabled:opacity-50 dark:border-neutral-700"
        >
          Sign out
        </button>
      </div>

      <div className="px-4 py-12 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-2xl dark:bg-neutral-800">
          🚗
        </div>
        <h2 className="mt-3 text-base font-semibold">Your garage is empty</h2>
        <p className="mx-auto mt-1 max-w-sm text-sm text-neutral-600 dark:text-neutral-400">
          Adding a vehicle is coming next. For now, this page exists to prove you are signed in.
        </p>
      </div>
    </div>
  );
}
