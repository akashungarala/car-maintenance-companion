import { AddVehicleForm } from './AddVehicleForm';

export const metadata = { title: 'Add a vehicle · Car Maintenance Companion' };

export default function AddVehiclePage() {
  return (
    // Capped at 640px: a wide form is a harder form to read.
    <main className="mx-auto flex min-h-screen max-w-[640px] flex-col justify-center px-4 py-8">
      <AddVehicleForm />
    </main>
  );
}
