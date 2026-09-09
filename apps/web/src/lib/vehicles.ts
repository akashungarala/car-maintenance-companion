/**
 * The vehicle shape, as the API returns it.
 *
 * Hand-written rather than imported from @cmc/api-types for now: the generated
 * types describe the whole OpenAPI document and pulling one response shape out
 * of them costs more indirection than it saves at this size. The generated
 * package is still the contract of record, and CI fails if it drifts — this is
 * a convenience alias over the same shape, not a second source of truth.
 */
export type Vehicle = {
  id: string;
  year: number;
  make: string;
  model: string;
  nickname: string | null;
  display_name: string;
  odometer: number;
  odometer_recorded_at: string;
  annual_mileage: number;
  created_at: string;
};

export function formatMiles(miles: number): string {
  return `${miles.toLocaleString('en-US')} miles`;
}
