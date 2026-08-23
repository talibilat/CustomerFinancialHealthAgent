import { expect, test } from '@playwright/test'

test('edits and previews a statement without changing confirmed history', async ({ page, request }) => {
  const confirmedBefore = await request.get('http://localhost:8000/overview')
  expect(confirmedBefore.ok()).toBeTruthy()
  const originalOverview = await confirmedBefore.json()

  await page.goto('/statement')
  const rentAmount = page.getByRole('textbox', { name: 'Rent amount' })
  await expect(rentAmount).toHaveValue('950.00')

  await rentAmount.fill('1200.00')
  const rentGroup = page.getByRole('group', { name: 'Outgoing: Rent' })
  await expect(rentGroup.getByText(/normalizes to/i)).toHaveCount(0)
  await expect(rentGroup.getByText(/£950\.00 per month/i)).toHaveCount(0)

  await page.getByRole('button', { name: 'Preview my position' }).click()
  await expect(page.getByRole('status')).toContainText('Preview updated')
  await expect(page.getByText('£681.25', { exact: true })).toBeVisible()

  const confirmedAfter = await request.get('http://localhost:8000/overview')
  expect(confirmedAfter.ok()).toBeTruthy()
  expect(await confirmedAfter.json()).toEqual(originalOverview)

  await rentAmount.fill('1300.00')
  await expect(page.getByText('Your position if you save this')).toHaveCount(0)
  await expect(page.getByText('£681.25', { exact: true })).toHaveCount(0)
})

test('keeps the statement editor usable at a 375px viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/statement')
  await expect(page.getByRole('textbox', { name: 'Rent amount' })).toBeVisible()

  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }))
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport)

  await page.getByRole('button', { name: 'Add an outgoing' }).click()
  await expect(page.getByRole('group', { name: 'Outgoing: New entry' })).toBeVisible()
  const afterAdd = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }))
  expect(afterAdd.document).toBeLessThanOrEqual(afterAdd.viewport)
})
