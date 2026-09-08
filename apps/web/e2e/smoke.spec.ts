import { expect, test } from '@playwright/test';

test('the home page renders', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Hello World');
  await expect(page).toHaveTitle('Car Maintenance Companion');
});

test('security headers are served', async ({ page }) => {
  // An F3 acceptance criterion, asserted rather than assumed. Header
  // regressions are silent and are otherwise found by a security review
  // months later.
  const response = await page.goto('/');
  const headers = response?.headers() ?? {};

  expect(headers['x-content-type-options']).toBe('nosniff');
  expect(headers['x-frame-options']).toBe('DENY');
  expect(headers['referrer-policy']).toBe('strict-origin-when-cross-origin');
  expect(headers['content-security-policy']).toContain("frame-ancestors 'none'");
  expect(headers['strict-transport-security']).toContain('max-age=');
});

test('the framework does not advertise itself', async ({ page }) => {
  const response = await page.goto('/');

  expect(response?.headers()['x-powered-by']).toBeUndefined();
});

test('an unknown route returns 404', async ({ page }) => {
  const response = await page.goto('/no-such-page');

  expect(response?.status()).toBe(404);
});
