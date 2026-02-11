import { test, expect } from '@playwright/test';

test('localhost:3000 serves the frontend', async ({ page }) => {
  const resp = await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });
  expect(resp).not.toBeNull();
  expect(resp.status()).toBeGreaterThanOrEqual(200);
  expect(resp.status()).toBeLessThan(400);
  await expect(page.locator('body')).toBeVisible();
});
