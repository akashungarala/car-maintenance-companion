import { expect, test } from '@playwright/test';

// UX-001's acceptance criteria, exercised as a person would: a real browser,
// a real build, real keyboard input. The API is intercepted because this is a
// frontend test — the backend's own behaviour is asserted in its test suite,
// and depending on a live API here would make this fail for reasons that have
// nothing to do with the page.
const APP = '/apps/car-maintenance-companion';
const ENDPOINT = '**/api/auth/magic-link';

test('a person can request a sign-in link', async ({ page }) => {
  await page.route(ENDPOINT, (route) =>
    route.fulfill({ status: 202, json: { status: 'accepted' } }),
  );

  await page.goto(`${APP}/signin`);
  await page.getByLabel(/email address/i).fill('sam@example.com');
  await page.getByRole('button', { name: /email me a link/i }).click();

  await expect(page.getByRole('heading', { name: /check your email/i })).toBeVisible();
  // The address is named so a typo is visible: the common failure here is not
  // an error, it is a link sent somewhere the user cannot read.
  await expect(page.getByText('sam@example.com')).toBeVisible();
});

test('the form is usable with the keyboard alone', async ({ page }) => {
  await page.route(ENDPOINT, (route) =>
    route.fulfill({ status: 202, json: { status: 'accepted' } }),
  );

  await page.goto(`${APP}/signin`);
  await page.getByLabel(/email address/i).focus();
  await page.keyboard.type('sam@example.com');
  await page.keyboard.press('Enter');

  await expect(page.getByRole('heading', { name: /check your email/i })).toBeVisible();
});

test('a malformed address never reaches the network', async ({ page }) => {
  let called = false;
  await page.route(ENDPOINT, (route) => {
    called = true;
    return route.fulfill({ status: 202, json: {} });
  });

  await page.goto(`${APP}/signin`);
  await page.getByLabel(/email address/i).fill('not-an-email');
  await page.getByRole('button', { name: /email me a link/i }).click();

  await expect(page.getByText(/does not look like an email address/i)).toBeVisible();
  expect(called).toBe(false);
});

test('a failure leaves the address in the field', async ({ page }) => {
  await page.route(ENDPOINT, (route) => route.fulfill({ status: 500, json: {} }));

  await page.goto(`${APP}/signin`);
  await page.getByLabel(/email address/i).fill('sam@example.com');
  await page.getByRole('button', { name: /email me a link/i }).click();

  await expect(page.getByText(/something went wrong/i)).toBeVisible();
  // Clearing it would make the user retype the address to retry.
  await expect(page.getByLabel(/email address/i)).toHaveValue('sam@example.com');
});

test('being rate limited says how long to wait', async ({ page }) => {
  await page.route(ENDPOINT, (route) =>
    route.fulfill({ status: 429, headers: { 'retry-after': '45' }, body: '' }),
  );

  await page.goto(`${APP}/signin`);
  await page.getByLabel(/email address/i).fill('sam@example.com');
  await page.getByRole('button', { name: /email me a link/i }).click();

  await expect(page.getByText(/45 seconds/i)).toBeVisible();
});
