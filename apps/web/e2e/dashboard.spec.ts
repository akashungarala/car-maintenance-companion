import { expect, test } from '@playwright/test';

// UX-006 in a real browser.
const APP = '/apps/car-maintenance-companion';
const PLAN = '**/api/vehicles/v1/plan';

const plan = (items: unknown[]) => ({
  vehicle_id: 'v1',
  estimated_mileage: 48200,
  items,
});

const OIL = {
  id: 'i1',
  name: 'Engine oil & filter',
  due_at: '2027-02-08',
  due_mileage: 53200,
  status: 'due_soon',
  is_assumed: true,
};

test('the dashboard groups items and says what it is assuming', async ({ page }) => {
  await page.route(PLAN, (route) =>
    route.fulfill({
      status: 200,
      json: plan([
        {
          ...OIL,
          id: 'a',
          name: 'Wash & interior clean',
          status: 'overdue',
          due_at: '2026-09-30',
          due_mileage: null,
        },
        OIL,
      ]),
    }),
  );

  await page.goto(`${APP}/garage/v1`);

  await expect(page.getByRole('heading', { name: /overdue/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /due soon/i })).toBeVisible();
  // Empty bands are not rendered.
  await expect(page.getByRole('heading', { name: /upcoming/i })).toHaveCount(0);
  // The most important line on the screen.
  await expect(page.getByText(/assumed/i).first()).toBeVisible();
  await expect(page.getByText(/8 February 2027/)).toBeVisible();
  await expect(page.getByText(/30 September 2026/)).toBeVisible();
});

test('an item with no due date reads "not scheduled"', async ({ page }) => {
  await page.route(PLAN, (route) =>
    route.fulfill({
      status: 200,
      json: plan([
        { ...OIL, name: 'Tire rotation', due_at: null, due_mileage: null, status: 'upcoming' },
      ]),
    }),
  );

  await page.goto(`${APP}/garage/v1`);

  await expect(page.getByText(/not scheduled/i)).toBeVisible();
});

test('a missing vehicle returns the visitor to the garage', async ({ page }) => {
  await page.route(PLAN, (route) => route.fulfill({ status: 404, json: {} }));
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ status: 200, json: { id: 'u1', email: 'sam@example.com' } }),
  );
  await page.route('**/api/vehicles', (route) => route.fulfill({ status: 200, json: [] }));

  await page.goto(`${APP}/garage/v1`);

  await expect(page).toHaveURL(new RegExp(`${APP}/garage$`));
});
