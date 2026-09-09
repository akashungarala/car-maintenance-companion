import { CallbackClient } from './CallbackClient';

export const metadata = { title: 'Signing in · Car Maintenance Companion' };

export default async function CallbackPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  // Read on the server and passed down, rather than useSearchParams in the
  // client component: it keeps the client component a pure function of its
  // props, which is what makes it testable without a router.
  const { token } = await searchParams;

  return (
    <main className="mx-auto flex min-h-screen max-w-[420px] flex-col justify-center px-4">
      <CallbackClient token={token} />
    </main>
  );
}
