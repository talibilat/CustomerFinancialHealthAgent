import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? 'http://localhost:8000'

test('completes the connected reviewer journey without hidden state', async ({ page, request }) => {
  const transition = await request.post(`${apiBaseUrl}/demo/reset`, {
    data: { preset: 'zero_income', confirmed_reset: true },
  })
  expect(transition.ok()).toBeTruthy()
  const reset = await request.post(`${apiBaseUrl}/demo/reset`, {
    data: { preset: 'repayment_near_buffer', confirmed_reset: true },
  })
  expect(reset.ok()).toBeTruthy()

  await page.goto('/overview')
  await page.getByRole('button', { name: 'Review how this was calculated' }).click()
  await expect(page.getByText(/monthly headroom = normalized monthly income/i)).toBeVisible()
  await expect(page.getByText(/calculation policy version/i)).toBeVisible()

  await page.getByRole('link', { name: 'Update my information' }).click()
  const rent = page.getByRole('group', { name: 'Outgoing: Rent' })
  await expect(rent.getByRole('combobox', { name: 'Rent category' })).toHaveValue('housing')
  await expect(rent.getByRole('combobox', { name: 'Rent treatment' })).toHaveValue('protected_outgoing')
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
  await page.getByRole('button', { name: 'Preview my position' }).click()
  await expect(page.getByText('Your position if you save this')).toBeVisible()
  await page.getByRole('checkbox', { name: /checked this information/i }).check()
  await page.getByRole('button', { name: 'Confirm this statement' }).click()
  await expect(page.getByText(/saved to your history/i)).toBeVisible()

  await page.getByRole('link', { name: 'History' }).click()
  await page.getByRole('button', { name: /view august 2026 statement details/i }).first().click()
  await expect(page.getByText('Weekend pottery', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /correct the august 2026 record/i }).click()
  await page.getByRole('textbox', { name: 'What was wrong' }).fill('Reviewer correction')
  await page.getByRole('button', { name: 'Save this correction' }).click()
  await expect(page.getByText('Reason given: Reviewer correction')).toBeVisible()

  await page.getByRole('link', { name: 'Explore a repayment' }).click()
  await page.getByRole('textbox', { name: 'Amount you are considering' }).fill('50.00')
  await page.getByRole('textbox', { name: /monthly buffer you want to keep/i }).fill('200.00')
  await page.getByRole('button', { name: 'Compare this repayment' }).click()
  await expect(page.getByRole('status')).toContainText('Comparison updated')
  await page.getByRole('button', { name: 'Save scenario' }).click()
  await expect(page.getByRole('status')).toContainText('Scenario saved')
  await expect(page.getByText('£50.00 repayment').first()).toBeVisible()

  await page.getByRole('link', { name: 'Overview' }).click()
  await page.getByRole('button', { name: 'Explain this more simply' }).click()
  await expect(page.getByText('Optional personalization is unavailable')).toBeVisible()
  await expect(page.getByText('How the reported figures compare')).toBeVisible()
})

test('recovers when the frontend becomes available before the backend', async ({ page }) => {
  await page.route(`${apiBaseUrl}/overview`, async (route) => {
    await route.abort('connectionrefused')
  })

  await page.goto('/overview')
  await expect(page.getByText("We can't reach the server right now")).toBeVisible()

  await page.unroute(`${apiBaseUrl}/overview`)
  await page.getByRole('button', { name: 'Try again' }).click()

  await expect(page.getByText('Your monthly position', { exact: true })).toBeVisible()
})

test('deep-linked customer pages pass automated accessibility checks', async ({ page }) => {
  for (const path of ['/overview', '/statement', '/history', '/repayment']) {
    await page.goto(path)
    await expect(page.getByRole('navigation', { name: 'Sections' })).toBeVisible()

    const results = await new AxeBuilder({ page }).analyze()
    expect(
      results.violations.map(({ id, impact, nodes }) => ({
        id,
        impact,
        nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })),
      })),
      `${path} should have no automated accessibility violations`,
    ).toEqual([])
  }
})

test('keyboard, zoom, contrast, and reduced-motion preferences preserve navigation', async ({
  page,
}) => {
  await page.setViewportSize({ width: 640, height: 800 })
  await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' })
  await page.goto('/overview')

  await page.keyboard.press('Tab')
  const firstLink = page.getByRole('link', { name: 'Overview' })
  await expect(firstLink).toBeFocused()
  const focusAppearance = await firstLink.evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      outlineStyle: style.outlineStyle,
      outlineWidth: Number.parseFloat(style.outlineWidth),
    }
  })
  expect(focusAppearance.outlineStyle).not.toBe('none')
  expect(focusAppearance.outlineWidth).toBeGreaterThan(0)

  await page.evaluate(() => {
    document.documentElement.style.zoom = '200%'
  })
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }))
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport)
  await expect(page.getByRole('link', { name: 'Explore a repayment' })).toBeVisible()

  const motion = await page.evaluate(() =>
    getComputedStyle(document.querySelector('nav a') as HTMLElement).transitionDuration,
  )
  expect(motion).toBe('0s')
})

test('refresh and back navigation preserve an unfinished statement draft with clear copy', async ({
  page,
}) => {
  await page.goto('/statement')
  const rentAmount = page.getByRole('textbox', { name: 'Rent amount' })
  await expect(rentAmount).toBeVisible()
  await rentAmount.fill('1234.56')

  await page.getByRole('link', { name: 'Overview' }).click()
  await page.goBack()
  await expect(rentAmount).toHaveValue('1234.56')

  await page.reload()
  await expect(rentAmount).toHaveValue('1234.56')
  await expect(page.getByRole('status')).toContainText('restored your unsaved changes')
})

test('long values reflow at narrow width and the statement has no keyboard trap', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 })
  await page.goto('/statement')
  const description = page.getByRole('textbox', { name: 'Rent description' })
  await description.fill(
    'Wohnkosten und weitere regelmaessige Ausgaben fuer die gemeinsam genutzte Familienwohnung',
  )

  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }))
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport)
  await expect(page.getByRole('button', { name: /remove wohnkosten/i })).toBeVisible()

  await page.locator('body').click({ position: { x: 1, y: 1 } })
  let reachedSave = false
  for (let index = 0; index < 100; index += 1) {
    await page.keyboard.press('Tab')
    reachedSave = await page.evaluate(
      () => document.activeElement?.textContent?.trim() === 'Save my statement',
    )
    if (reachedSave) break
  }
  expect(reachedSave).toBeTruthy()
  await expect(page.getByRole('button', { name: 'Save my statement' })).toBeFocused()
})
