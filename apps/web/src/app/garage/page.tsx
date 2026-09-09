import { GarageClient } from './GarageClient';

export const metadata = { title: 'Your garage · Car Maintenance Companion' };

export default function GaragePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-[640px] flex-col justify-center px-4">
      <GarageClient />
    </main>
  );
}
