import '@testing-library/jest-dom/vitest';

import { afterAll, afterEach, beforeAll } from 'vitest';

import { server } from './src/mocks/node';

// onUnhandledRequest: 'error' is the point of wiring MSW this early. Any
// accidental real network call from a test fails loudly instead of silently
// hitting the internet and producing a flaky, slow, non-deterministic suite.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
