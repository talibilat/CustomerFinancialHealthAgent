import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { RepaymentExplorer } from './RepaymentExplorer'
import { previewRepaymentScenarioRepaymentScenarioPreviewPost } from '@/api/generated'

vi.mock('@/api/generated', () => ({
  previewRepaymentScenarioRepaymentScenarioPreviewPost: vi.fn(),
}))

const preview = vi.mocked(previewRepaymentScenarioRepaymentScenarioPreviewPost)

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
  preview.mockResolvedValue(ok(result()))
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
      screen.queryByRole('textbox', { name: /amount you pay now/i }),
    ).not.toBeInTheDocument()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: /what to compare/i }), 'change_existing')

    expect(screen.getByRole('textbox', { name: /amount you pay now/i })).toBeInTheDocument()
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

    expect(await screen.findByText('protected_buffer_missing')).toBeInTheDocument()
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
})
