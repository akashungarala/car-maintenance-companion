import { expect, test } from '@playwright/test';

// UX-002 in a real browser. The API is intercepted: the backend's own rules are
// asserted in its suite, and this test is about what the page does with each
// answer.
const APP = '/apps/car-maintenance-companion';
const ENDPOINT = '**/api/auth/session';

test('a valid link signs in and moves on', async ({ page }) => {
  await page.route(ENDPOINT, (route) =>
    route.fulfill({ status: 200, json: { status: 'signed_in' } }),
  );

  await page.goto(`${APP}/auth/callback?token=valid-token`);

  // The destination is the app, not this page: success here is not being seen.
  await expect(page).toHaveURL(new RegExp(`${APP}/?$`));
});

test('a spent link shows the generic message', async ({ page }) => {
  await page.route(ENDPOINT, (route) => route.fulfill({ status: 401, json: {} }));

  await page.goto(`${APP}/auth/callback?token=already-used`);

  await expect(page.getByRole('heading', { name: /cannot be used/i })).toBeVisible();
  await expect(page.getByRole('link', { name: /request a new link/i })).toBeVisible();
});

test('a bookmarked callback with no token says the same thing', async ({ page }) => {
  await page.goto(`${APP}/auth/callback`);

  await expect(page.getByRole('heading', { name: /cannot be used/i })).toBeVisible();
});

test('merely loading the page issues no GET that could spend the link', async ({ page }) => {
  // The defence against mail scanners: they prefetch with GET, and nothing the
  // page does on a GET consumes anything. Only the POST spends the token.
  const methods: string[] = [];
  await page.route(ENDPOINT, (route) => {
    methods.push(route.request().method());
    return route.fulfill({ status: 200, json: { status: 'signed_in' } });
  });

  await page.goto(`${APP}/auth/callback?token=valid-token`);
  await page.waitForURL(new RegExp(`${APP}/?$`));

  expect(methods).toEqual(['POST']);
});
