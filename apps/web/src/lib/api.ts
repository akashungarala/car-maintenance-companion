/**
 * Where the API lives.
 *
 * A relative path, not an absolute URL. The frontend and the API are served
 * under the same origin through the portfolio's path prefix, so a hardcoded
 * host would break the moment the domain or prefix changed — and would need a
 * CORS policy that currently does not have to exist.
 */
export const API_BASE =
  process.env['NEXT_PUBLIC_API_BASE'] ?? '/apps/car-maintenance-companion/api';

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}
