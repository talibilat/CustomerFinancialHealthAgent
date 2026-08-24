import { expect, test } from '@playwright/test'

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? 'http://localhost:8000'

test.beforeEach(async ({ request }) => {
  // Force a transition before loading the stable statement fixture because
  // selecting the already-active preset is intentionally idempotent.
  const transition = await request.post(`${apiBaseUrl}/demo/reset`, {
    data: { preset: 'zero_income', confirmed_reset: true },
  })
  expect(transition.ok()).toBeTruthy()

  const reset = await request.post(`${apiBaseUrl}/demo/reset`, {
    data: { preset: 'repayment_near_buffer', confirmed_reset: true },
  })
  expect(reset.ok()).toBeTruthy()
})

test('edits and previews a statement without changing confirmed history', async ({ page, request }) => {
  const confirmedBefore = await request.get(`${apiBaseUrl}/overview`)
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

  const confirmedAfter = await request.get(`${apiBaseUrl}/overview`)
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

test('invalid statement keeps every entered value and links every error to its control', async ({ page }) => {
  await page.goto('/statement')
  const wagesAmount = page.getByRole('textbox', { name: 'Wages amount' })
  const rentAmount = page.getByRole('textbox', { name: 'Rent amount' })
  await expect(wagesAmount).toBeVisible()

  await wagesAmount.fill('-5.00')
  await rentAmount.fill('NaN')
  await page.getByRole('button', { name: 'Save my statement' }).click()

  const summary = page.getByRole('alert', { name: 'There is a problem' })
  await expect(summary).toBeFocused()
  const negativeAmountLink = summary.getByRole('link', {
    name: 'Enter an amount of zero or more.',
  })
  const nonFiniteAmountLink = summary.getByRole('link', { name: 'Enter a real amount.' })
  await expect(negativeAmountLink).toBeVisible()
  await expect(nonFiniteAmountLink).toBeVisible()

  const wagesTarget = await negativeAmountLink.getAttribute('href')
  const rentTarget = await nonFiniteAmountLink.getAttribute('href')
  expect(wagesTarget).toBeTruthy()
  expect(rentTarget).toBeTruthy()
  await expect(wagesAmount).toHaveAttribute('id', wagesTarget!.slice(1))
  await expect(rentAmount).toHaveAttribute('id', rentTarget!.slice(1))
  await expect(wagesAmount).toHaveValue('-5.00')
  await expect(rentAmount).toHaveValue('NaN')
})

test('stale statement refreshes from the current saved values', async ({ page, context }) => {
  const otherPage = await context.newPage()
  await page.goto('/statement')
  await otherPage.goto('/statement')

  const staleRentAmount = page.getByRole('textbox', { name: 'Rent amount' })
  const currentRentAmount = otherPage.getByRole('textbox', { name: 'Rent amount' })
  await expect(staleRentAmount).toBeVisible()
  await expect(currentRentAmount).toBeVisible()

  await currentRentAmount.fill('1111.00')
  await otherPage.getByRole('button', { name: 'Save my statement' }).click()
  await expect(otherPage.getByRole('status')).toContainText('Your statement was saved')

  await staleRentAmount.fill('999.00')
  await page.getByRole('button', { name: 'Save my statement' }).click()
  await expect(page.getByText(/refresh to see the current version/i)).toBeVisible()
  await expect(staleRentAmount).toHaveValue('999.00')

  await page.getByRole('button', { name: 'Refresh this statement' }).click()
  await expect(staleRentAmount).toHaveValue('1111.00')
})

test('manual classification path stays completable and visible in history', async ({ page }) => {
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
  await pottery.getByRole('combobox', { name: 'Weekend pottery category' }).selectOption('leisure_and_hobbies')
  await pottery.getByRole('combobox', { name: 'Weekend pottery treatment' }).selectOption('flexible_living_cost')
  await page.getByRole('button', { name: 'Save my statement' }).click()
  await expect(page.getByRole('status')).toContainText('Your statement was saved')

  await page.getByRole('button', { name: 'Preview my position' }).click()
  await expect(page.getByRole('status')).toContainText('Preview updated')
  await page.getByRole('checkbox', { name: /checked this information/i }).check()
  await page.getByRole('button', { name: 'Confirm this statement' }).click()
  await expect(page.getByText(/this statement is saved to your history/i)).toBeVisible()

  await page.getByRole('link', { name: 'History' }).click()
  await page
    .getByRole('button', { name: /view august 2026 statement details/i })
    .first()
    .click()
  await expect(page.getByText('Weekend pottery', { exact: true })).toBeVisible()

  await page.getByRole('link', { name: 'Update my information' }).click()
  await page.getByRole('button', { name: 'Remove Weekend pottery' }).click()
  await page.getByRole('button', { name: 'Save my statement' }).click()
  await expect(page.getByRole('status')).toContainText('Your statement was saved')
})

test('saved scenario keeps its original values after its basis is corrected', async ({
  page,
  request,
}) => {
  await page.goto('/repayment')
  await page
    .getByRole('textbox', { name: 'Amount you are considering' })
    .fill('123.45')
  await page
    .getByRole('textbox', { name: /monthly buffer you want to keep/i })
    .fill('200.00')
  await page.getByRole('button', { name: 'Compare this repayment' }).click()
  await expect(page.getByRole('status')).toContainText('Comparison updated')
  await page.getByRole('button', { name: 'Save scenario' }).click()
  await expect(page.getByRole('status')).toContainText('Scenario saved')

  const savedAmount = page.getByText('£123.45 repayment').first()
  const savedCard = savedAmount.locator('xpath=ancestor::*[@data-slot="card"][1]')
  await expect(savedCard).toContainText(/based on your confirmed .* statement/i)
  const originalCardText = await savedCard.textContent()
  const originalHeadroom = originalCardText?.match(/[-£\d,.]+ headroom afterwards/)?.[0]
  expect(originalHeadroom).toBeTruthy()

  const scenarios = await request.get(`${apiBaseUrl}/repayment-scenarios`)
  expect(scenarios.ok()).toBeTruthy()
  const saved = (await scenarios.json()).scenarios.find(
    (scenario: { proposed_repayment: string }) => scenario.proposed_repayment === '123.45',
  )
  expect(saved).toBeTruthy()

  const statementResponse = await request.get(
    `${apiBaseUrl}/financial-statement?statement_period=${saved.basis_statement_period}`,
  )
  expect(statementResponse.ok()).toBeTruthy()
  const editable = (await statementResponse.json()).statement
  const entry = (item: {
    entry_id: string
    description: string
    original_amount: string
    original_frequency: string
    classification: null | { display_category: string; outgoing_treatment: string }
  }) => ({
    entry_id: item.entry_id,
    description: item.description,
    amount:
      item.description === 'Rent'
        ? (Number(item.original_amount) + 1).toFixed(2)
        : item.original_amount,
    frequency: item.original_frequency,
    classification: item.classification?.display_category
      ? {
          display_category: item.classification.display_category,
          outgoing_treatment: item.classification.outgoing_treatment,
          remember: false,
        }
      : null,
  })
  const correction = await request.post(
    `${apiBaseUrl}/history/${saved.basis_snapshot_id}/correct`,
    {
      headers: { 'Idempotency-Key': `e2e-correct-${saved.basis_snapshot_id}` },
      data: {
        statement_period: editable.statement_period,
        currency: editable.currency,
        income_entries: editable.income_entries.map(entry),
        outgoing_entries: editable.outgoing_entries.map(entry),
        repayment_commitments: editable.repayment_commitments.map(entry),
        resilience: editable.resilience,
        looking_ahead: {
          irregular_costs: editable.looking_ahead.irregular_costs.map(entry),
          protected_future_provisions:
            editable.looking_ahead.protected_future_provisions.map(entry),
          expected_changes: editable.looking_ahead.expected_changes.map(
            (change: {
              entry_id: string
              description: string
              kind: string
              original_amount: string
              original_frequency: string
            }) => ({
              entry_id: change.entry_id,
              description: change.description,
              kind: change.kind,
              amount: change.original_amount,
              frequency: change.original_frequency,
            }),
          ),
        },
        correction_reason: 'The rent amount was one pound too low.',
      },
    },
  )
  expect(correction.ok()).toBeTruthy()

  await page.reload()
  const unchangedCard = page
    .getByText('£123.45 repayment')
    .first()
    .locator('xpath=ancestor::*[@data-slot="card"][1]')
  await expect(unchangedCard).toContainText('This basis statement was later corrected')
  await expect(unchangedCard).toContainText(
    'This saved scenario still uses the original statement and values',
  )
  await expect(unchangedCard).toContainText(originalHeadroom as string)
})
