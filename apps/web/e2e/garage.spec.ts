import { expect, test } from '@playwright/test';

// UX-003 in a real browser.
const APP = '/apps/car-maintenance-companion';
const ME = '**/api/auth/me';
const SESSION = '**/api/auth/session';

test('a signed-in visitor sees the address they signed in with', async ({ page }) => {
  await page.route(ME, (route) =>
    route.fulfill({ status: 200, json: { id: 'u1', email: 'sam@example.com' } }),
  );

  await page.goto(`${APP}/garage`);

  await expect(page.getByText('sam@example.com')).toBeVisible();
  await expect(page.getByRole('button', { name: /sign out/i })).toBeVisible();
});

test('an unauthenticated visitor is sent to sign in', async ({ page }) => {
  await page.route(ME, (route) => route.fulfill({ status: 401, json: {} }));

  await page.goto(`${APP}/garage`);

  await expect(page).toHaveURL(new RegExp(`${APP}/signin`));
});

test('a server error offers a retry rather than bouncing to sign in', async ({ page }) => {
  await page.route(ME, (route) => route.fulfill({ status: 500, json: {} }));

  await page.goto(`${APP}/garage`);

  await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`${APP}/garage`));
});

test('signing out revokes server-side and returns to sign in', async ({ page }) => {
  const methods: string[] = [];
  await page.route(ME, (route) =>
    route.fulfill({ status: 200, json: { id: 'u1', email: 'sam@example.com' } }),
  );
  await page.route(SESSION, (route) => {
    methods.push(route.request().method());
    return route.fulfill({ status: 204, body: '' });
  });

  await page.goto(`${APP}/garage`);
  await page.getByRole('button', { name: /sign out/i }).click();

  await expect(page).toHaveURL(new RegExp(`${APP}/signin`));
  // A DELETE, not just a cleared cookie: the session must stop working for
  // anyone who captured it.
  expect(methods).toEqual(['DELETE']);
});
