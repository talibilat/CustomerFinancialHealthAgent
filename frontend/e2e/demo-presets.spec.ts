import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? 'http://localhost:8000'

async function loadPreset(page: Page, request: APIRequestContext, label: string) {
  const transition = await request.post(`${apiBaseUrl}/demo/reset`, {
    data: { preset: 'mixed_resilience', confirmed_reset: true },
  })
  expect(transition.ok()).toBeTruthy()

  await page.goto('/overview')
  await page.getByLabel('Demonstration preset').selectOption({ label })
  const resetWarning = page.getByRole('alert').filter({
    hasText: 'Fictional demo data will be reset',
  })
  await expect(resetWarning).toBeVisible()
  await page.getByRole('button', { name: `Load ${label}` }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Fictional demo data loaded.' })).toBeVisible()
}

test('zero-income preset shows an exact shortfall and deterministic support', async ({ page, request }) => {
  await loadPreset(page, request, 'Zero income')

  await expect(page.getByText('No monthly income is reported')).toBeVisible()
  await expect(
    page.getByRole('status').filter({ hasText: 'No monthly income is reported' }),
  ).toContainText('monthly shortfall of £650.00')
  await expect(page.getByRole('link', { name: 'Review your information' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Contact Ophelos support' })).toBeVisible()
  await expect(page.getByRole('link', { name: /free independent debt advice/i })).toBeVisible()
})

test('reported-shortfall preset preserves the penny and all living costs', async ({ page, request }) => {
  await loadPreset(page, request, 'Reported shortfall')

  await expect(page.getByText('Reported outgoings are above income')).toBeVisible()
  await expect(page.getByText(/exact monthly shortfall of £0.01/i)).toBeVisible()
  await expect(page.getByText(/every reported living cost remains part of this result/i)).toBeVisible()
})

test('protected-outgoings preset explains those costs before repayment exploration', async ({ page, request }) => {
  await loadPreset(page, request, 'Protected outgoings not covered')

  await expect(page.getByText('Reported income does not cover protected outgoings')).toBeVisible()
  await expect(page.getByText(/protected monthly outgoings are £1,050.00/i)).toBeVisible()
  await expect(page.getByText(/reported monthly income of £900.00/i)).toBeVisible()
})

test('Azure-unavailable preset keeps manual classification and deterministic results usable', async ({ page, request }) => {
  await loadPreset(page, request, 'Azure unavailable')
  await page.goto('/statement')

  const pottery = page.getByRole('group', { name: /outgoing: weekend pottery/i })
  await expect(pottery).toBeVisible()
  await expect(pottery.getByText(/we will not guess on your behalf/i)).toBeVisible()
  await expect(pottery.getByText('Optional suggestion')).toHaveCount(0)
  await expect(pottery.getByLabel(/category/i)).toHaveValue('')
  await expect(pottery.getByLabel(/treatment/i)).toHaveValue('')
})
