import { DashboardClient } from './DashboardClient';

export const metadata = { title: 'Your car · Car Maintenance Companion' };

export default async function VehiclePage({ params }: { params: Promise<{ vehicleId: string }> }) {
  const { vehicleId } = await params;

  return (
    <main className="mx-auto flex min-h-screen max-w-[720px] flex-col justify-center px-4 py-8">
      <DashboardClient vehicleId={vehicleId} />
    </main>
  );
}
