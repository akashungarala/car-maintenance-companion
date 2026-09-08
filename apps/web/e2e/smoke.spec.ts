import { expect, test } from '@playwright/test';

// The app is served under this prefix everywhere — locally, on Vercel, and
// proxied at akashungarala.com. Tests navigate to it explicitly because a
// leading-slash path would be resolved against the origin and skip it.
const APP = '/apps/car-maintenance-companion';

test('the home page renders', async ({ page }) => {
  await page.goto(APP);

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Hello World');
  await expect(page).toHaveTitle('Car Maintenance Companion');
});

test('security headers are served', async ({ page }) => {
  // An F3 acceptance criterion, asserted rather than assumed. Header
  // regressions are silent and are otherwise found by a security review
  // months later.
  const response = await page.goto(APP);
  const headers = response?.headers() ?? {};

  expect(headers['x-content-type-options']).toBe('nosniff');
  expect(headers['x-frame-options']).toBe('DENY');
  expect(headers['referrer-policy']).toBe('strict-origin-when-cross-origin');
  expect(headers['content-security-policy']).toContain("frame-ancestors 'none'");
});

test('the framework does not advertise itself', async ({ page }) => {
  const response = await page.goto(APP);

  expect(response?.headers()['x-powered-by']).toBeUndefined();
});

test('an unknown route returns 404', async ({ page }) => {
  const response = await page.goto(`${APP}/no-such-page`);

  expect(response?.status()).toBe(404);
});

test('nothing is served outside the base path', async ({ page }) => {
  // The proxy maps /apps/car-maintenance-companion 1:1. Serving anything at the
  // domain root would mean the prefix is not actually applied, and assets would
  // break once proxied.
  const response = await page.goto('/');

  expect(response?.status()).toBe(404);
});

test('static assets resolve under the base path', async ({ page }) => {
  const failed: string[] = [];
  page.on('response', (r) => {
    if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`);
  });

  await page.goto(APP);
  await page.waitForLoadState('networkidle');

  expect(failed).toEqual([]);
});
