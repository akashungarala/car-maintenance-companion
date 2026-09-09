export type PlanStatus = 'overdue' | 'due_soon' | 'upcoming';

export type PlanItem = {
  id: string;
  name: string;
  due_at: string | null;
  due_mileage: number | null;
  status: PlanStatus;
  is_assumed: boolean;
};

export type Plan = {
  vehicle_id: string;
  estimated_mileage: number;
  items: PlanItem[];
};

/**
 * Written out, never 08/02/27 — which is two different days depending on where
 * the reader lives, and this screen's whole job is being believed.
 */
export function formatDueDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export const BANDS: { status: PlanStatus; label: string }[] = [
  { status: 'overdue', label: 'Overdue' },
  { status: 'due_soon', label: 'Due soon' },
  { status: 'upcoming', label: 'Upcoming' },
];
