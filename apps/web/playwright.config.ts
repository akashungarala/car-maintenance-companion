import { defineConfig, devices } from '@playwright/test';

const PORT = 3100;
// Origin only. baseURL must NOT include the basePath: Playwright resolves
// page.goto('/foo') with URL semantics, so a leading slash discards any path on
// the base and the test silently hits the wrong URL. Specs navigate to the
// prefix explicitly instead.
const baseURL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env['CI']),
  retries: process.env['CI'] ? 1 : 0,
  reporter: process.env['CI'] ? [['github'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

  // Runs against a real production build, not the dev server: dev-only
  // behaviour (unminified output, relaxed headers) would make these tests
  // prove something other than what ships.
  webServer: {
    // `next start` is incompatible with output: 'standalone'. Running the
    // standalone server is also higher fidelity — it is byte-for-byte what
    // the container image runs.
    command: [
      'BUILD_STANDALONE=1 pnpm exec next build',
      'cp -r .next/static .next/standalone/apps/web/.next/',
      `PORT=${PORT} node .next/standalone/apps/web/server.js`,
    ].join(' && '),
    url: `${baseURL}/apps/car-maintenance-companion`,
    reuseExistingServer: !process.env['CI'],
    timeout: 180_000,
  },
});
