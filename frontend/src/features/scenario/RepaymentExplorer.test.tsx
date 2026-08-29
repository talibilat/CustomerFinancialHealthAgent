import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { RepaymentExplorer } from './RepaymentExplorer'
import {
  listSavedScenariosRepaymentScenariosGet,
  previewRepaymentScenarioRepaymentScenarioPreviewPost,
  retrieveScenarioBasisRepaymentScenarioBasisGet,
  saveScenarioRepaymentScenariosPost,
} from '@/api/generated'

vi.mock('@/api/generated', () => ({
  listSavedScenariosRepaymentScenariosGet: vi.fn(),
  previewRepaymentScenarioRepaymentScenarioPreviewPost: vi.fn(),
  retrieveScenarioBasisRepaymentScenarioBasisGet: vi.fn(),
  saveScenarioRepaymentScenariosPost: vi.fn(),
}))

const preview = vi.mocked(previewRepaymentScenarioRepaymentScenarioPreviewPost)
const retrieveBasis = vi.mocked(retrieveScenarioBasisRepaymentScenarioBasisGet)
const listSaved = vi.mocked(listSavedScenariosRepaymentScenariosGet)
const saveScenario = vi.mocked(saveScenarioRepaymentScenariosPost)

function ok(data: unknown) {
  return {
    data,
    error: undefined,
    request: new Request('http://localhost/repayment-scenario/preview'),
    response: new Response(null, { status: 200 }),
  } as never
}

function result(overrides = {}) {
  return {
    calculation_policy_version: 'scenario-policy-v1',
    basis_snapshot_id: 'snap-1',
    basis_statement_period: '2026-08-01',
    basis_monthly_headroom: '931.25',
    mode: 'additional',
    proposed_repayment: '100.00',
    replaced_repayment: null,
    scenario_headroom: '831.25',
    protected_monthly_buffer: null,
    buffer_shortfall: null,
    result_code: 'may_leave_limited_room',
    warnings: ['protected_buffer_missing'],
    ...overrides,
  }
}

function saved(overrides = {}) {
  return {
    id: 'scenario-1',
    basis_snapshot_id: 'snap-1',
    basis_statement_period: '2026-08-01',
    basis_is_superseded: false,
    mode: 'additional',
    selected_existing_commitment_id: null,
    selected_existing_commitment_description: null,
    proposed_repayment: '100.00',
    protected_monthly_buffer: null,
    basis_monthly_headroom: '931.25',
    replaced_repayment: null,
    scenario_headroom: '831.25',
    buffer_shortfall: null,
    result_code: 'may_leave_limited_room',
    warnings: ['protected_buffer_missing'],
    calculation_policy_version: 'scenario-policy-v1',
    created_at: '2026-08-24T10:00:00Z',
    ...overrides,
  }
}

function renderExplorer() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <RepaymentExplorer />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  preview.mockReset()
  retrieveBasis.mockReset()
  listSaved.mockReset()
  saveScenario.mockReset()
  preview.mockResolvedValue(ok(result()))
  retrieveBasis.mockResolvedValue(
    ok({
      basis_snapshot_id: 'snap-1',
      basis_statement_period: '2026-08-01',
      basis_monthly_headroom: '931.25',
      existing_repayment_commitments: [
        {
          id: 'commitment-row-1',
          description: 'Credit card repayment',
          normalized_monthly_amount: '75.25',
        },
      ],
    }),
  )
  listSaved.mockResolvedValue(ok({ scenarios: [], total: 0 }))
  saveScenario.mockResolvedValue(ok(saved()))
})

describe('RepaymentExplorer', () => {
  it('never pre-fills an amount, so nothing is recommended', () => {
    renderExplorer()

    expect(screen.getByRole('textbox', { name: /amount you are considering/i })).toHaveValue('')
  })

  it('shows the basis snapshot the comparison is made against', async () => {
    renderExplorer()
    await userEvent.type(screen.getByRole('textbox', { name: /amount you are considering/i }), '100.00')
    await userEvent.click(screen.getByRole('button', { name: /compare/i }))

    expect(await screen.findByText(/august 2026/i)).toBeInTheDocument()
    expect(screen.getByText('£931.25')).toBeInTheDocument()
  })

  it('shows the resulting headroom and the qualified wording', async () => {
    renderExplorer()
    await userEvent.type(screen.getByRole('textbox', { name: /amount you are considering/i }), '100.00')
    await userEvent.click(screen.getByRole('button', { name: /compare/i }))

    expect(await screen.findByText('£831.25')).toBeInTheDocument()
    expect(screen.getByText(/may leave limited room/i)).toBeInTheDocument()
  })

  it('clears an earlier comparison when the mode changes', async () => {
    renderExplorer()
    await userEvent.type(screen.getByRole('textbox', { name: /amount you are considering/i }), '100.00')
    await userEvent.click(screen.getByRole('button', { name: /compare/i }))
    await screen.findByText('£831.25')

    await userEvent.selectOptions(screen.getByRole('combobox', { name: /what to compare/i }), 'change_existing')

    expect(screen.queryByText('£831.25')).not.toBeInTheDocument()
    // The amount from the other mode must not leak into this one.
    expect(screen.getByRole('textbox', { name: /amount you are considering/i })).toHaveValue('')
  })

  it('asks which commitment is being changed only in change-existing mode', async () => {
    renderExplorer()

    expect(
      screen.queryByRole('combobox', { name: /repayment to change/i }),
    ).not.toBeInTheDocument()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: /what to compare/i }), 'change_existing')

    expect(await screen.findByRole('combobox', { name: /repayment to change/i })).toBeInTheDocument()
  })

  it('surfaces a rejected amount against its own field', async () => {
    preview.mockResolvedValue({
      data: undefined,
      error: {
        detail: {
          code: 'statement_invalid',
          message: 'Nothing was saved. Check the highlighted fields and try again.',
          errors: [
            {
              field: 'proposed_repayment',
              code: 'amount_negative',
              message: 'Enter an amount of zero or more.',
            },
          ],
        },
      },
      request: new Request('http://localhost/repayment-scenario/preview'),
      response: new Response(null, { status: 422 }),
    } as never)

    renderExplorer()
    await userEvent.type(screen.getByRole('textbox', { name: /amount you are considering/i }), '-5')
    await userEvent.click(screen.getByRole('button', { name: /compare/i }))

    expect(await screen.findByText(/enter an amount of zero or more/i)).toBeInTheDocument()
  })

  it('reports a missing buffer as a limitation', async () => {
    renderExplorer()
    await userEvent.type(screen.getByRole('textbox', { name: /amount you are considering/i }), '100.00')
    await userEvent.click(screen.getByRole('button', { name: /compare/i }))

    expect(await screen.findByText(/no protected monthly buffer has been provided/i)).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('protected_buffer_missing')
  })

  it('states plainly that this changes nothing and is not advice', async () => {
    renderExplorer()
    await userEvent.type(screen.getByRole('textbox', { name: /amount you are considering/i }), '100.00')
    await userEvent.click(screen.getByRole('button', { name: /compare/i }))

    await screen.findByText('£831.25')
    const bodyText = document.body.textContent ?? ''

    expect(bodyText).toMatch(/nothing here changes/i)
    expect(bodyText).not.toMatch(/we recommend|you should pay|affordable/i)
  })

  it('announces the comparison through a status message', async () => {
    renderExplorer()
    await userEvent.type(screen.getByRole('textbox', { name: /amount you are considering/i }), '100.00')
    await userEvent.click(screen.getByRole('button', { name: /compare/i }))

    expect(await screen.findByRole('status')).toHaveTextContent(/comparison/i)
  })

  it('keeps a comparison temporary until the customer explicitly saves it', async () => {
    renderExplorer()
    await userEvent.type(screen.getByRole('textbox', { name: /amount you are considering/i }), '100.00')
    await userEvent.click(screen.getByRole('button', { name: /compare/i }))
    await screen.findByText('£831.25')

    expect(saveScenario).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: /save scenario/i }))

    expect(saveScenario).toHaveBeenCalledWith(
      expect.objectContaining({
        body: {
          basis_snapshot_id: 'snap-1',
          mode: 'additional',
          selected_existing_commitment_id: null,
          proposed_repayment: '100.00',
          protected_monthly_buffer: null,
        },
        headers: { 'Idempotency-Key': expect.any(String) },
      }),
    )
    expect(await screen.findByRole('status')).toHaveTextContent(/scenario saved/i)
  })

  it('saves a changed repayment against the selected stored commitment', async () => {
    preview.mockResolvedValue(
      ok(
        result({
          mode: 'change_existing',
          proposed_repayment: '125.25',
          replaced_repayment: '75.25',
          scenario_headroom: '881.25',
        }),
      ),
    )
    saveScenario.mockResolvedValue(
      ok(
        saved({
          mode: 'change_existing',
          selected_existing_commitment_id: 'commitment-row-1',
          selected_existing_commitment_description: 'Credit card repayment',
          proposed_repayment: '125.25',
          replaced_repayment: '75.25',
          scenario_headroom: '881.25',
        }),
      ),
    )
    renderExplorer()
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /what to compare/i }),
      'change_existing',
    )
    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: /repayment to change/i }),
      'commitment-row-1',
    )
    await userEvent.type(
      screen.getByRole('textbox', { name: /amount you are considering/i }),
      '125.25',
    )
    await userEvent.click(screen.getByRole('button', { name: /compare/i }))
    await userEvent.click(await screen.findByRole('button', { name: /save scenario/i }))

    expect(saveScenario).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          mode: 'change_existing',
          selected_existing_commitment_id: 'commitment-row-1',
        }),
      }),
    )
  })

  it('shows saved values, their original basis, and a superseded-basis notice in plain text', async () => {
    listSaved.mockResolvedValue(
      ok({
        scenarios: [saved({ basis_is_superseded: true })],
        total: 1,
      }),
    )

    renderExplorer()

    expect(await screen.findByRole('heading', { name: /saved scenarios/i })).toBeInTheDocument()
    expect(screen.getByText(/based on your confirmed august 2026 statement/i)).toBeInTheDocument()
    expect(screen.getByText(/basis statement was later corrected/i)).toBeInTheDocument()
    expect(screen.getByText(/£100.00 repayment/i)).toBeInTheDocument()
    expect(screen.getByText(/£831.25 headroom afterwards/i)).toBeInTheDocument()
  })
})
