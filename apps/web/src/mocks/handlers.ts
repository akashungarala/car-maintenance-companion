import type { RequestHandler } from 'msw';

/**
 * Request handlers shared by tests and the browser worker.
 *
 * Empty in F3: Phase 0 has no product API to mock. Handlers arrive with the
 * first real endpoint, typed from the generated OpenAPI types so the mocks
 * cannot drift from the contract.
 */
export const handlers: RequestHandler[] = [];
