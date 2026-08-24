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
  await expect(page.getByText('Your position if you save this')).toBeVisible()

  const confirmedAfter = await request.get('http://localhost:8000/overview')
  expect(confirmedAfter.ok()).toBeTruthy()
  expect(await confirmedAfter.json()).toEqual(originalOverview)

  await rentAmount.fill('1300.00')
  await expect(page.getByText('Your position if you save this')).toHaveCount(0)
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

test('manual classification fallback keeps confirmation complete without Azure', async ({ page }) => {
  await page.goto('/statement')
  await expect(page.getByRole('textbox', { name: 'Rent amount' })).toBeVisible()

  const stalePotteryRows = page.getByRole('button', { name: 'Remove Weekend pottery' })
  if ((await stalePotteryRows.count()) > 0) {
    while ((await stalePotteryRows.count()) > 0) {
      await stalePotteryRows.first().click()
    }
    await page.getByRole('button', { name: 'Save my statement' }).click()
    await expect(page.getByRole('status')).toContainText('Your statement was saved')
  }

  await page.getByRole('button', { name: 'Add an outgoing' }).click()

  const newEntry = page.getByRole('group', { name: 'Outgoing: New entry' })
  await newEntry.getByRole('textbox', { name: 'New entry description' }).fill('Weekend pottery')
  const pottery = page.getByRole('group', { name: 'Outgoing: Weekend pottery' })
  await pottery.getByRole('textbox', { name: 'Weekend pottery amount' }).fill('25.00')
  await page.getByRole('button', { name: 'Save my statement' }).click()
  await expect(page.getByRole('status')).toContainText('Your statement was saved')

  await expect(pottery.getByText(/tell us what this was for/i)).toBeVisible()
  await expect(pottery.getByText(/optional suggestion/i)).toHaveCount(0)
  await pottery.getByRole('combobox', { name: 'Weekend pottery category' }).selectOption('leisure_and_hobbies')
  await pottery.getByRole('combobox', { name: 'Weekend pottery treatment' }).selectOption('flexible_living_cost')
  await page.getByRole('button', { name: 'Save my statement' }).click()
  await expect(page.getByRole('status')).toContainText('Your statement was saved')

  await page.getByRole('button', { name: 'Preview my position' }).click()
  await expect(page.getByRole('status')).toContainText('Preview updated')
  await page.getByRole('checkbox', { name: /checked this information/i }).check()
  await page.getByRole('button', { name: 'Confirm this statement' }).click()
  await expect(page.getByText(/this statement is saved to your history/i)).toBeVisible()

  await page.reload()
  await page.getByRole('button', { name: 'Remove Weekend pottery' }).click()
  await page.getByRole('button', { name: 'Save my statement' }).click()
  await expect(page.getByRole('status')).toContainText('Your statement was saved')
})
