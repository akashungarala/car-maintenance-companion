import { expect, test } from '@playwright/test';

// UX-004 and UX-005 in a real browser.
const APP = '/apps/car-maintenance-companion';
const ME = '**/api/auth/me';
const VEHICLES = '**/api/vehicles';

const SIGNED_IN = { id: 'u1', email: 'sam@example.com' };
const CIVIC = {
  id: 'v1',
  year: 2019,
  make: 'Honda',
  model: 'Civic',
  nickname: 'The Civic',
  display_name: 'The Civic',
  odometer: 48200,
  odometer_recorded_at: '2026-09-09T00:00:00Z',
  annual_mileage: 12000,
  created_at: '2026-09-09T00:00:00Z',
};

test('an empty garage explains what to do', async ({ page }) => {
  await page.route(ME, (route) => route.fulfill({ status: 200, json: SIGNED_IN }));
  await page.route(VEHICLES, (route) => route.fulfill({ status: 200, json: [] }));

  await page.goto(`${APP}/garage`);

  await expect(page.getByRole('heading', { name: /add your first car/i })).toBeVisible();
  await expect(page.getByRole('link', { name: /add a vehicle/i })).toBeVisible();
});

test('a garage with vehicles lists them', async ({ page }) => {
  await page.route(ME, (route) => route.fulfill({ status: 200, json: SIGNED_IN }));
  await page.route(VEHICLES, (route) => route.fulfill({ status: 200, json: [CIVIC] }));

  await page.goto(`${APP}/garage`);

  await expect(page.getByRole('heading', { name: 'The Civic' })).toBeVisible();
  await expect(page.getByText('48,200 miles')).toBeVisible();
});

test('a person can add a vehicle and land back in the garage', async ({ page }) => {
  let posted: Record<string, unknown> = {};
  await page.route(ME, (route) => route.fulfill({ status: 200, json: SIGNED_IN }));
  await page.route(VEHICLES, (route) => {
    if (route.request().method() === 'POST') {
      posted = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({ status: 201, json: CIVIC });
    }
    return route.fulfill({ status: 200, json: [CIVIC] });
  });

  await page.goto(`${APP}/garage/add`);
  await page.getByLabel(/^year/i).fill('2019');
  await page.getByLabel(/^make/i).fill('Honda');
  await page.getByLabel(/^model/i).fill('Civic');
  await page.getByLabel(/current mileage/i).fill('48200');
  await page.getByRole('button', { name: /add vehicle/i }).click();

  await expect(page).toHaveURL(new RegExp(`${APP}/garage`));
  // "Average" preselected, so the driving question could be skipped entirely.
  expect(posted['annual_mileage']).toBe(12000);
});

test('validation stops an impossible year before it reaches the API', async ({ page }) => {
  let called = false;
  await page.route(VEHICLES, (route) => {
    called = true;
    return route.fulfill({ status: 201, json: CIVIC });
  });

  await page.goto(`${APP}/garage/add`);
  await page.getByLabel(/^year/i).fill('219');
  await page.getByRole('button', { name: /add vehicle/i }).click();

  await expect(page.getByText(/between 1900 and/i)).toBeVisible();
  expect(called).toBe(false);
});
