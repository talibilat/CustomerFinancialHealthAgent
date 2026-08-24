import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { StatementEditor } from './StatementEditor'
import {
  previewFinancialStatementFinancialStatementPreviewPost,
  retrieveFinancialStatementFinancialStatementGet,
  updateFinancialStatementFinancialStatementPut,
  confirmFinancialStatementFinancialStatementConfirmPost,
} from '@/api/generated'

vi.mock('@/api/generated', () => ({
  retrieveFinancialStatementFinancialStatementGet: vi.fn(),
  updateFinancialStatementFinancialStatementPut: vi.fn(),
  previewFinancialStatementFinancialStatementPreviewPost: vi.fn(),
  confirmFinancialStatementFinancialStatementConfirmPost: vi.fn(),
}))

const retrieve = vi.mocked(retrieveFinancialStatementFinancialStatementGet)
const update = vi.mocked(updateFinancialStatementFinancialStatementPut)
const preview = vi.mocked(previewFinancialStatementFinancialStatementPreviewPost)
const confirmStatement = vi.mocked(confirmFinancialStatementFinancialStatementConfirmPost)

type ClassificationFixture = {
  display_category: string | null
  outgoing_treatment: string | null
  source: string | null
  taxonomy_version: string
  requires_confirmation: boolean
  reason_code: string | null
  suggestion?: {
    display_category: string
    outgoing_treatment: string
    confidence: string
    reason: string
    requires_clarification: boolean
  } | null
}

function entry(entryId: string, description: string, amount: string, frequency: string, normalized: string) {
  return {
    entry_id: entryId,
    description,
    original_amount: amount,
    original_frequency: frequency,
    normalized_monthly_amount: normalized,
    classification: null as ClassificationFixture | null,
  }
}

function statementResponse(overrides = {}) {
  return {
    version: 1,
    updated_at: '2026-08-01T09:00:00Z',
    statement: {
      statement_period: '2026-08-01',
      currency: 'GBP',
      income_entries: [entry('i1', 'Wages', '2450.00', 'monthly', '2450.00')],
      outgoing_entries: [
        entry('o1', 'Rent', '950.00', 'monthly', '950.00'),
        entry('o2', 'Food and housekeeping', '120.00', 'weekly', '520.00'),
      ],
      repayment_commitments: [],
      resilience: {
        accessible_savings: '300.00',
        protected_reserve: '1000.00',
        current_account_balance: '-45.30',
        known_arrears: null,
      },
      looking_ahead: {
        irregular_costs: [],
        protected_future_provisions: [],
        expected_changes: [],
      },
      ...overrides,
    },
  }
}

function ok(data: unknown) {
  return {
    data,
    error: undefined,
    request: new Request('http://localhost/financial-statement'),
    response: new Response(null, { status: 200 }),
  } as never
}

function failure(status: number, detail: unknown) {
  return {
    data: undefined,
    error: { detail },
    request: new Request('http://localhost/financial-statement'),
    response: new Response(null, { status }),
  } as never
}

function renderEditor() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <StatementEditor statementPeriod="2026-08-01" />
    </QueryClientProvider>,
  )
}

async function amountField(name: RegExp) {
  return screen.findByRole('textbox', { name })
}

beforeEach(() => {
  retrieve.mockReset()
  update.mockReset()
  preview.mockReset()
  confirmStatement.mockReset()
  retrieve.mockResolvedValue(ok(statementResponse()))
})

describe('StatementEditor', () => {
  it('shows every reported amount with its original frequency beside the monthly value', async () => {
    renderEditor()

    expect(await amountField(/rent amount/i)).toHaveValue('950.00')
    expect(screen.getByRole('combobox', { name: /rent frequency/i })).toHaveValue('monthly')

    const food = screen.getByRole('group', { name: /food and housekeeping/i })
    expect(within(food).getByText(/£520\.00 per month/i)).toBeInTheDocument()
  })

  it('never pairs an edited amount with a stale normalized monthly value', async () => {
    renderEditor()

    const rent = await amountField(/rent amount/i)
    await userEvent.clear(rent)
    await userEvent.type(rent, '1200.00')

    const rentGroup = screen.getByRole('group', { name: /outgoing: rent/i })
    expect(within(rentGroup).queryByText(/normalizes to/i)).not.toBeInTheDocument()
    expect(within(rentGroup).queryByText(/£950\.00 per month/i)).not.toBeInTheDocument()
  })

  it('previews the recalculated position and states that nothing was saved', async () => {
    preview.mockResolvedValue(
      ok({
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '3000.00',
        normalized_monthly_outgoings: '1470.00',
        monthly_headroom: '1530.00',
        result_code: 'surplus',
        warnings: [],
        normalized_monthly_repayment_commitments: '0.00',
        normalized_monthly_irregular_costs: '0.00',
        normalized_monthly_protected_future_provisions: '0.00',
        expected_changes: [],
        resilience: {
          accessible_savings: '300.00',
          protected_reserve: '1000.00',
          current_account_balance: '-45.30',
          known_arrears: null,
          savings_above_reserve: '0.00',
          reserve_gap: '700.00',
          result_code: 'below_reserve',
          warnings: [],
        },
      }),
    )

    renderEditor()

    const wages = await amountField(/wages amount/i)
    await userEvent.clear(wages)
    await userEvent.type(wages, '3000.00')
    await userEvent.click(screen.getByRole('button', { name: /preview/i }))

    expect((await screen.findAllByText('£1,530.00')).length).toBeGreaterThan(0)
    expect(
      screen.getByText(/nothing has been saved and your confirmed history has not changed/i),
    ).toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()
  })

  it('clears a preview as soon as the draft changes', async () => {
    preview.mockResolvedValue(
      ok({
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '3000.00',
        normalized_monthly_outgoings: '1470.00',
        monthly_headroom: '1530.00',
        result_code: 'surplus',
        warnings: [],
        normalized_monthly_repayment_commitments: '0.00',
        normalized_monthly_irregular_costs: '0.00',
        normalized_monthly_protected_future_provisions: '0.00',
        expected_changes: [],
        resilience: {
          accessible_savings: '300.00',
          protected_reserve: '1000.00',
          current_account_balance: '-45.30',
          known_arrears: null,
          savings_above_reserve: '0.00',
          reserve_gap: '700.00',
          result_code: 'below_reserve',
          warnings: [],
        },
      }),
    )

    renderEditor()
    const wages = await amountField(/wages amount/i)
    await userEvent.click(screen.getByRole('button', { name: /preview/i }))
    expect((await screen.findAllByText('£1,530.00')).length).toBeGreaterThan(0)

    await userEvent.clear(wages)
    await userEvent.type(wages, '3100.00')

    expect(screen.queryByText('£1,530.00')).not.toBeInTheDocument()
    expect(screen.queryByText(/your position if you save this/i)).not.toBeInTheDocument()
  })

  it('preserves unsaved edits when the window regains focus', async () => {
    renderEditor()
    const wages = await amountField(/wages amount/i)
    await userEvent.clear(wages)
    await userEvent.type(wages, '3000.00')

    retrieve.mockResolvedValue(
      ok(
        statementResponse({
          income_entries: [entry('i1', 'Wages', '999.00', 'monthly', '999.00')],
        }),
      ),
    )

    focusManager.setFocused(false)
    focusManager.setFocused(true)
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(screen.getByRole('textbox', { name: /wages amount/i })).toHaveValue('3000.00')
    expect(retrieve).toHaveBeenCalledTimes(1)
    focusManager.setFocused(undefined)
  })

  it('adds and removes a reported outgoing', async () => {
    renderEditor()
    await amountField(/rent amount/i)

    await userEvent.click(screen.getByRole('button', { name: /add an outgoing/i }))
    expect(screen.getAllByRole('group', { name: /outgoing/i })).toHaveLength(3)

    await userEvent.click(screen.getByRole('button', { name: /remove rent/i }))
    expect(screen.queryByRole('textbox', { name: /rent amount/i })).not.toBeInTheDocument()
  })

  it('lists every invalid field, moves focus to the summary, and preserves what was entered', async () => {
    update.mockResolvedValue(
      failure(422, {
        code: 'statement_invalid',
        message: 'Nothing was saved. Check the highlighted fields and try again.',
        errors: [
          { field: 'income_entries.0.amount', code: 'amount_negative', message: 'Enter an amount of zero or more.' },
          { field: 'outgoing_entries.1.frequency', code: 'frequency_not_supported', message: 'Choose one of the supported frequencies.' },
        ],
      }),
    )

    renderEditor()

    const wages = await amountField(/wages amount/i)
    await userEvent.clear(wages)
    await userEvent.type(wages, '-5.00')
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    const summary = await screen.findByRole('alert', { name: /there is a problem/i })
    expect(summary).toHaveFocus()
    expect(within(summary).getByText(/enter an amount of zero or more/i)).toBeInTheDocument()
    expect(within(summary).getByText(/choose one of the supported frequencies/i)).toBeInTheDocument()
    expect(screen.getByText(/nothing was saved/i)).toBeInTheDocument()

    // The customer's typed value survives the rejected submission.
    expect(screen.getByRole('textbox', { name: /wages amount/i })).toHaveValue('-5.00')
  })

  it('links each error summary item back to the control it refers to', async () => {
    update.mockResolvedValue(
      failure(422, {
        code: 'statement_invalid',
        message: 'Nothing was saved.',
        errors: [
          { field: 'income_entries.0.amount', code: 'amount_negative', message: 'Enter an amount of zero or more.' },
        ],
      }),
    )

    renderEditor()
    await amountField(/wages amount/i)
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    const link = await screen.findByRole('link', { name: /enter an amount of zero or more/i })
    const target = document.querySelector(link.getAttribute('href') as string)

    expect(target).toBe(screen.getByRole('textbox', { name: /wages amount/i }))
    expect(target).toHaveAttribute('aria-describedby', 'field-income_entries-i1-amount-error')
  })

  it('keeps an entry error attached to that entry after an earlier row is removed', async () => {
    update.mockResolvedValue(
      failure(422, {
        code: 'statement_invalid',
        message: 'Nothing was saved.',
        errors: [
          {
            field: 'outgoing_entries.1.amount',
            code: 'amount_invalid',
            message: 'Enter a valid food amount.',
          },
        ],
      }),
    )

    renderEditor()
    await amountField(/rent amount/i)
    await userEvent.click(screen.getByRole('button', { name: /save/i }))
    await screen.findByRole('link', { name: /enter a valid food amount/i })

    await userEvent.click(screen.getByRole('button', { name: /remove rent/i }))

    const foodAmount = screen.getByRole('textbox', { name: /food and housekeeping amount/i })
    const link = screen.getByRole('link', { name: /enter a valid food amount/i })
    expect(document.querySelector(link.getAttribute('href') as string)).toBe(foodAmount)
    expect(foodAmount).toHaveAccessibleDescription(/enter a valid food amount/i)
  })

  it('renders FastAPI generated validation details as actionable field errors', async () => {
    update.mockResolvedValue(
      failure(422, [
        {
          type: 'decimal_parsing',
          loc: ['body', 'income_entries', 0, 'amount'],
          msg: 'Input should be a valid decimal.',
          input: 'not-money',
        },
      ]),
    )

    renderEditor()
    await amountField(/wages amount/i)
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    const link = await screen.findByRole('link', { name: /input should be a valid decimal/i })
    expect(document.querySelector(link.getAttribute('href') as string)).toBe(
      screen.getByRole('textbox', { name: /wages amount/i }),
    )
  })

  it('offers a safe refresh when the statement was changed elsewhere', async () => {
    update.mockResolvedValue(
      failure(409, {
        code: 'statement_version_conflict',
        message: 'Someone changed this statement. Refresh to see the current version.',
        current_version: 2,
      }),
    )

    renderEditor()
    await amountField(/wages amount/i)
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    expect(await screen.findByText(/refresh to see the current version/i)).toBeInTheDocument()

    retrieve.mockResolvedValue(ok({ ...statementResponse(), version: 2 }))
    await userEvent.click(screen.getByRole('button', { name: /refresh/i }))

    expect(await screen.findByRole('textbox', { name: /wages amount/i })).toHaveValue('2450.00')
  })

  it('announces a successful save through a status message', async () => {
    update.mockResolvedValue(ok({ ...statementResponse(), version: 2 }))

    renderEditor()
    await amountField(/wages amount/i)
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    expect(await screen.findByRole('status')).toHaveTextContent(/saved/i)
  })

  it('is operable with the keyboard alone', async () => {
    renderEditor()
    await amountField(/wages amount/i)

    await userEvent.tab()
    expect(document.activeElement).toHaveAttribute('id')

    // Reaching and activating a control without a pointer.
    screen.getByRole('button', { name: /add an outgoing/i }).focus()
    await userEvent.keyboard('{Enter}')

    expect(screen.getAllByRole('group', { name: /outgoing/i })).toHaveLength(3)
  })

  it('treats resilience and looking-ahead information as optional', async () => {
    retrieve.mockResolvedValue(
      ok(
        statementResponse({
          resilience: {
            accessible_savings: null,
            protected_reserve: null,
            current_account_balance: null,
            known_arrears: null,
          },
        }),
      ),
    )

    renderEditor()

    expect(await screen.findByRole('textbox', { name: /accessible savings/i })).toHaveValue('')
    expect(
      screen.getByText(/leaving these blank creates a limitation rather than an assumed value/i),
    ).toBeInTheDocument()
    // An empty optional section must not block the core statement.
    expect(screen.getByRole('button', { name: /preview/i })).toBeEnabled()
  })

  it('never describes the previewed position as proof of affordability', async () => {
    preview.mockResolvedValue(
      ok({
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '2450.00',
        normalized_monthly_outgoings: '1470.00',
        monthly_headroom: '980.00',
        result_code: 'surplus',
        warnings: ['looking_ahead_info_missing'],
        normalized_monthly_repayment_commitments: '0.00',
        normalized_monthly_irregular_costs: '0.00',
        normalized_monthly_protected_future_provisions: '0.00',
        expected_changes: [],
        resilience: {
          accessible_savings: null,
          protected_reserve: null,
          current_account_balance: null,
          known_arrears: null,
          savings_above_reserve: null,
          reserve_gap: null,
          result_code: null,
          warnings: ['resilience_info_missing'],
        },
      }),
    )

    renderEditor()
    await amountField(/wages amount/i)
    await userEvent.click(screen.getByRole('button', { name: /preview/i }))

    await screen.findAllByText('£980.00')
    const bodyText = document.body.textContent ?? ''

    expect(bodyText).not.toMatch(/you can afford/i)
    expect(bodyText).not.toMatch(/\bhealthy\b/i)
    expect(bodyText).toMatch(/not a proof of long-term affordability/i)
    expect(screen.getByText('looking_ahead_info_missing')).toBeInTheDocument()
  })
})

describe('StatementEditor expected changes', () => {
  function withExpectedChange() {
    const response = statementResponse()
    response.statement.looking_ahead.expected_changes = [
      {
        entry_id: 'e1',
        description: 'Shift reduction',
        kind: 'income_decrease',
        original_amount: '200.00',
        original_frequency: 'monthly',
        normalized_monthly_amount: '200.00',
      },
    ] as never
    return response
  }

  it('shows a reported expected change with the kind the customer chose', async () => {
    retrieve.mockResolvedValue(ok(withExpectedChange()))

    renderEditor()

    expect(await screen.findByRole('textbox', { name: /shift reduction amount/i })).toHaveValue('200.00')
    expect(screen.getByRole('combobox', { name: /shift reduction kind/i })).toHaveValue('income_decrease')
  })

  it('never discards a stored expected change when the statement is saved', async () => {
    retrieve.mockResolvedValue(ok(withExpectedChange()))
    update.mockResolvedValue(ok(withExpectedChange()))

    renderEditor()
    await screen.findByRole('textbox', { name: /shift reduction amount/i })
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    const body = update.mock.calls[0][0].body as {
      looking_ahead: { expected_changes: { description: string; kind: string; amount: string }[] }
    }
    expect(body.looking_ahead.expected_changes).toEqual([
      expect.objectContaining({
        description: 'Shift reduction',
        kind: 'income_decrease',
        amount: '200.00',
      }),
    ])
  })

  it('adds and removes an expected change', async () => {
    renderEditor()
    await screen.findByRole('textbox', { name: /wages amount/i })

    await userEvent.click(screen.getByRole('button', { name: /add an expected change/i }))
    expect(screen.getAllByRole('group', { name: /expected change/i })).toHaveLength(1)

    await userEvent.click(screen.getByRole('button', { name: /remove new entry/i }))
    expect(screen.queryByRole('group', { name: /expected change/i })).not.toBeInTheDocument()
  })
})

describe('StatementEditor classification', () => {
  function classified(overrides = {}) {
    return {
      display_category: 'housing',
      outgoing_treatment: 'protected_outgoing',
      source: 'deterministic_rule',
      taxonomy_version: 'outgoing-taxonomy-v1',
      requires_confirmation: false,
      reason_code: null,
      ...overrides,
    }
  }

  function withClassifications() {
    const response = statementResponse()
    response.statement.outgoing_entries[0].classification = classified() as never
    response.statement.outgoing_entries[1].classification = classified({
      display_category: null,
      outgoing_treatment: null,
      source: null,
      requires_confirmation: true,
      reason_code: 'description_ambiguous',
    }) as never
    response.statement.income_entries[0].classification = null as never
    return response
  }

  it('shows what a recognised outgoing was understood as', async () => {
    retrieve.mockResolvedValue(ok(withClassifications()))

    renderEditor()

    expect(await screen.findByRole('combobox', { name: /rent category/i })).toHaveValue('housing')
    expect(screen.getByRole('combobox', { name: /rent treatment/i })).toHaveValue('protected_outgoing')
  })

  it('asks the customer about an outgoing it could not work out, without guessing', async () => {
    retrieve.mockResolvedValue(ok(withClassifications()))

    renderEditor()

    const food = await screen.findByRole('combobox', { name: /food and housekeeping category/i })
    expect(food).toHaveValue('')
    expect(
      screen.getByText(/tell us what this was for/i),
    ).toBeInTheDocument()
  })

  it('presents a provider proposal as optional and waits for the customer to accept it', async () => {
    const response = withClassifications()
    response.statement.outgoing_entries[1].classification = classified({
      display_category: null,
      outgoing_treatment: null,
      source: null,
      requires_confirmation: true,
      reason_code: 'description_unknown',
      suggestion: {
        display_category: 'leisure_and_hobbies',
        outgoing_treatment: 'flexible_living_cost',
        confidence: '0.82',
        reason: 'Usually a hobby.',
        requires_clarification: false,
      },
    }) as never
    retrieve.mockResolvedValue(ok(response))

    renderEditor()

    const category = await screen.findByRole('combobox', {
      name: /food and housekeeping category/i,
    })
    const treatment = screen.getByRole('combobox', {
      name: /food and housekeeping treatment/i,
    })
    expect(category).toHaveValue('')
    expect(treatment).toHaveValue('')
    expect(screen.getByText(/optional suggestion/i)).toBeInTheDocument()
    expect(screen.getByText(/82% confidence/i)).toBeInTheDocument()
    expect(screen.getByText('Usually a hobby.')).toBeInTheDocument()

    await userEvent.click(
      screen.getByRole('button', { name: /use this suggestion for food and housekeeping/i }),
    )

    expect(category).toHaveValue('leisure_and_hobbies')
    expect(treatment).toHaveValue('flexible_living_cost')
  })

  it('does not ask about income at all', async () => {
    retrieve.mockResolvedValue(ok(withClassifications()))

    renderEditor()
    await screen.findByRole('combobox', { name: /rent category/i })

    expect(screen.queryByRole('combobox', { name: /wages category/i })).not.toBeInTheDocument()
  })

  it('sends a correction only for the entry the customer actually changed', async () => {
    retrieve.mockResolvedValue(ok(withClassifications()))
    update.mockResolvedValue(ok(withClassifications()))

    renderEditor()
    const food = await screen.findByRole('combobox', { name: /food and housekeeping category/i })
    await userEvent.selectOptions(food, 'food_and_housekeeping')
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /food and housekeeping treatment/i }),
      'protected_outgoing',
    )
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    const body = update.mock.calls[0][0].body as {
      outgoing_entries: { description: string; classification?: unknown }[]
    }
    expect(body.outgoing_entries[0].classification).toBeUndefined()
    expect(body.outgoing_entries[1].classification).toEqual(
      expect.objectContaining({ display_category: 'food_and_housekeeping' }),
    )
  })

  it('can remember a correction for future statements', async () => {
    retrieve.mockResolvedValue(ok(withClassifications()))
    update.mockResolvedValue(ok(withClassifications()))

    renderEditor()
    const food = await screen.findByRole('combobox', { name: /food and housekeeping category/i })
    await userEvent.selectOptions(food, 'food_and_housekeeping')
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /food and housekeeping treatment/i }),
      'protected_outgoing',
    )
    await userEvent.click(
      screen.getByRole('checkbox', { name: /remember this for food and housekeeping/i }),
    )
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    const body = update.mock.calls[0][0].body as {
      outgoing_entries: { classification?: { remember?: boolean } }[]
    }
    expect(body.outgoing_entries[1].classification?.remember).toBe(true)
  })

  it('changing the category does not silently change the treatment', async () => {
    retrieve.mockResolvedValue(ok(withClassifications()))

    renderEditor()
    const category = await screen.findByRole('combobox', { name: /rent category/i })
    await userEvent.selectOptions(category, 'leisure_and_hobbies')

    expect(screen.getByRole('combobox', { name: /rent treatment/i })).toHaveValue('protected_outgoing')
  })

  it('describes flexible spending as a real cost rather than spare money', async () => {
    retrieve.mockResolvedValue(ok(withClassifications()))

    renderEditor()
    await screen.findByRole('combobox', { name: /rent category/i })

    const bodyText = document.body.textContent ?? ''
    expect(bodyText).not.toMatch(/disposable/i)
    expect(bodyText).not.toMatch(/spare money/i)
    expect(bodyText).not.toMatch(/non-essential/i)
    expect(bodyText).toMatch(/flexible living cost/i)
  })

  it('surfaces a rejected classification against its own field', async () => {
    retrieve.mockResolvedValue(ok(withClassifications()))
    update.mockResolvedValue(
      failure(422, {
        code: 'statement_invalid',
        message: 'Nothing was saved. Check the highlighted fields and try again.',
        errors: [
          {
            field: 'outgoing_entries.1.classification.display_category',
            code: 'category_not_supported',
            message: 'Choose one of the supported categories.',
          },
        ],
      }),
    )

    renderEditor()
    await screen.findByRole('combobox', { name: /rent category/i })
    await userEvent.click(screen.getByRole('button', { name: /save/i }))

    const summary = await screen.findByRole('alert', { name: /there is a problem/i })
    expect(summary).toHaveFocus()
    const link = within(summary).getByRole('link', { name: /choose one of the supported categories/i })
    expect(document.querySelector(link.getAttribute('href') as string)).toBe(
      screen.getByRole('combobox', { name: /food and housekeeping category/i }),
    )
  })
})

describe('StatementEditor confirmation', () => {
  const previewPayload = (overrides = {}) => ({
    calculation_policy_version: 'normalization-policy-v1',
    normalized_monthly_income: '2450.00',
    normalized_monthly_outgoings: '1518.75',
    monthly_headroom: '931.25',
    result_code: 'surplus',
    warnings: [],
    normalized_monthly_repayment_commitments: '0.00',
    normalized_monthly_irregular_costs: '0.00',
    normalized_monthly_protected_future_provisions: '0.00',
    expected_changes: [],
    resilience: {
      accessible_savings: null,
      protected_reserve: null,
      current_account_balance: null,
      known_arrears: null,
      savings_above_reserve: null,
      reserve_gap: null,
      result_code: null,
      warnings: [],
    },
    unresolved_classifications: [],
    can_confirm: true,
    ...overrides,
  })

  async function previewThen(overrides = {}) {
    preview.mockResolvedValue(ok(previewPayload(overrides)))
    renderEditor()
    await screen.findByRole('textbox', { name: /wages amount/i })
    await userEvent.click(screen.getByRole('button', { name: /preview/i }))
    await screen.findAllByText('£931.25')
  }

  it('offers confirmation only after a preview', async () => {
    renderEditor()
    await screen.findByRole('textbox', { name: /wages amount/i })

    expect(screen.queryByRole('button', { name: /confirm this statement/i })).not.toBeInTheDocument()
  })

  it('withholds confirmation while an outgoing still needs the customer', async () => {
    await previewThen({ unresolved_classifications: ['o2'], can_confirm: false })

    expect(screen.getByRole('button', { name: /confirm this statement/i })).toBeDisabled()
    expect(screen.getByText(/tell us what each outgoing was for/i)).toBeInTheDocument()
  })

  it('requires the customer to say they checked the information', async () => {
    await previewThen()

    expect(screen.getByRole('button', { name: /confirm this statement/i })).toBeDisabled()

    await userEvent.click(screen.getByRole('checkbox', { name: /checked this information/i }))

    expect(screen.getByRole('button', { name: /confirm this statement/i })).toBeEnabled()
  })

  it('never claims the information was independently verified', async () => {
    await previewThen()

    const bodyText = document.body.textContent ?? ''
    expect(bodyText).not.toMatch(/verified/i)
    expect(bodyText).toMatch(/believe it reflects/i)
  })

  it('confirms once and explains that corrections create new snapshots', async () => {
    confirmStatement.mockResolvedValue(
      ok({
        snapshot_id: 'snap-1',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-24T10:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        taxonomy_version: 'outgoing-taxonomy-v1',
        normalized_monthly_income: '2450.00',
        normalized_monthly_outgoings: '1518.75',
        monthly_headroom: '931.25',
        result_code: 'surplus',
        warnings: [],
        income_entries: [],
        outgoing_entries: [],
        resilience: previewPayload().resilience,
      }),
    )
    await previewThen()
    await userEvent.click(screen.getByRole('checkbox', { name: /checked this information/i }))

    await userEvent.click(screen.getByRole('button', { name: /confirm this statement/i }))

    expect(await screen.findByText(/this statement is saved to your history/i)).toBeInTheDocument()
    expect(screen.getByText(/corrections create a new snapshot/i)).toBeInTheDocument()
  })

  it('a double click sends one confirmation with one reference', async () => {
    let resolveConfirm: (value: unknown) => void = () => {}
    confirmStatement.mockReturnValue(
      new Promise((resolve) => {
        resolveConfirm = resolve
      }) as never,
    )
    await previewThen()
    await userEvent.click(screen.getByRole('checkbox', { name: /checked this information/i }))

    const button = screen.getByRole('button', { name: /confirm this statement/i })
    await userEvent.click(button)
    await userEvent.click(button)

    expect(confirmStatement).toHaveBeenCalledTimes(1)
    resolveConfirm(ok({ snapshot_id: 'snap-1' }))
  })

  it('explains a version conflict without losing what was entered', async () => {
    confirmStatement.mockResolvedValue(
      failure(409, {
        code: 'statement_version_conflict',
        message: 'This statement changed. Preview it again before confirming.',
        current_version: 2,
      }),
    )
    await previewThen()
    await userEvent.click(screen.getByRole('checkbox', { name: /checked this information/i }))
    await userEvent.click(screen.getByRole('button', { name: /confirm this statement/i }))

    expect(await screen.findByText(/preview it again before confirming/i)).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /wages amount/i })).toHaveValue('2450.00')
  })
})
