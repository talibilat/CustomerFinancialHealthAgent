import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { StatementEditor } from './StatementEditor'
import {
  previewFinancialStatementFinancialStatementPreviewPost,
  retrieveFinancialStatementFinancialStatementGet,
  updateFinancialStatementFinancialStatementPut,
} from '@/api/generated'

vi.mock('@/api/generated', () => ({
  retrieveFinancialStatementFinancialStatementGet: vi.fn(),
  updateFinancialStatementFinancialStatementPut: vi.fn(),
  previewFinancialStatementFinancialStatementPreviewPost: vi.fn(),
}))

const retrieve = vi.mocked(retrieveFinancialStatementFinancialStatementGet)
const update = vi.mocked(updateFinancialStatementFinancialStatementPut)
const preview = vi.mocked(previewFinancialStatementFinancialStatementPreviewPost)

function entry(entryId: string, description: string, amount: string, frequency: string, normalized: string) {
  return {
    entry_id: entryId,
    description,
    original_amount: amount,
    original_frequency: frequency,
    normalized_monthly_amount: normalized,
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

    expect(await screen.findByText('£1,530.00')).toBeInTheDocument()
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
    expect(await screen.findByText('£1,530.00')).toBeInTheDocument()

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

    await screen.findByText('£980.00')
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
