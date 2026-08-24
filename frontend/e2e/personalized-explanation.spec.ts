import { expect, test } from '@playwright/test'


test('optional wording fallback never replaces deterministic results or support', async ({ page }) => {
  await page.goto('/overview')
  await page.getByLabel('Demonstration preset').selectOption({ label: 'Zero income' })
  await page.getByRole('button', { name: 'Load Zero income' }).click()
  await expect(page.getByText('No monthly income is reported')).toBeVisible()

  const deterministic = page.getByText(/reported monthly income is £0.00/i)
  await expect(deterministic).toBeVisible()
  await page.getByRole('button', { name: 'Explain this more simply' }).click()

  await expect(page.getByText('Optional personalization is unavailable')).toBeVisible()
  await expect(deterministic).toBeVisible()
  await expect(page.getByRole('link', { name: 'Review your information' })).toBeVisible()
  await expect(page.getByRole('link', { name: /free independent debt advice/i })).toBeVisible()

  await page.reload()
  await expect(page.getByText('Optional personalization is unavailable')).toBeVisible()
  await expect(page.getByText(/reported monthly income is £0.00/i)).toBeVisible()
  await expect(page.getByRole('link', { name: /free independent debt advice/i })).toBeVisible()
})
