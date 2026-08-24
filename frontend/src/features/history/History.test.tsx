import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { History } from './History'
import { getHistoryHistoryGet } from '@/api/generated'

vi.mock('@/api/generated', () => ({ getHistoryHistoryGet: vi.fn() }))

const getHistory = vi.mocked(getHistoryHistoryGet)

function ok(data: unknown) {
  return {
    data,
    error: undefined,
    request: new Request('http://localhost/history'),
    response: new Response(null, { status: 200 }),
  } as never
}

function snapshot(period: string, headroom: string, income: string, outgoings: string) {
  return {
    snapshot_id: `snap-${period}`,
    statement_period: period,
    confirmed_at: `${period}T09:00:00Z`,
    calculation_policy_version: 'normalization-policy-v1',
    normalized_monthly_income: income,
    normalized_monthly_outgoings: outgoings,
    monthly_headroom: headroom,
    result_code: 'surplus',
    warnings: [],
    income_entries: [],
    outgoing_entries: [],
  }
}

function seriesPoint(period: string, headroom: string) {
  return {
    statement_period: period,
    normalized_monthly_income: '2450.00',
    normalized_monthly_outgoings: '950.00',
    monthly_headroom: headroom,
    result_code: 'surplus',
  }
}

function historyResponse(overrides = {}) {
  return {
    total: 2,
    limit: 50,
    offset: 0,
    snapshots: [
      snapshot('2026-08-01', '1600.00', '2600.00', '1000.00'),
      snapshot('2026-07-01', '1500.00', '2450.00', '950.00'),
    ],
    series: [seriesPoint('2026-07-01', '1500.00'), seriesPoint('2026-08-01', '1600.00')],
    latest_change: {
      is_baseline: false,
      previous_period: '2026-07-01',
      current_period: '2026-08-01',
      monthly_headroom_change: '100.00',
      increases: [
        {
          description: 'Wages',
          section: 'income',
          previous_monthly: '2450.00',
          current_monthly: '2600.00',
          signed_headroom_effect: '150.00',
        },
      ],
      decreases: [
        {
          description: 'Rent',
          section: 'outgoing',
          previous_monthly: '950.00',
          current_monthly: '1000.00',
          signed_headroom_effect: '-50.00',
        },
      ],
      warnings: [],
    },
    ...overrides,
  }
}

function renderHistory() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <History />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getHistory.mockReset()
  getHistory.mockResolvedValue(ok(historyResponse()))
})

describe('History', () => {
  it('shows an actionable empty state rather than implying zero income', async () => {
    getHistory.mockResolvedValue(
      ok({ total: 0, limit: 50, offset: 0, snapshots: [], series: [], latest_change: null }),
    )

    renderHistory()

    expect(await screen.findByText(/nothing confirmed yet/i)).toBeInTheDocument()
    const bodyText = document.body.textContent ?? ''
    expect(bodyText).not.toMatch(/£0\.00/)
  })

  it('presents the series as a readable table with exact values', async () => {
    renderHistory()

    const table = await screen.findByRole('table', { name: /monthly headroom over time/i })
    const rows = within(table).getAllByRole('row')

    expect(within(rows[1]).getByText('£1,500.00')).toBeInTheDocument()
    expect(within(rows[2]).getByText('£1,600.00')).toBeInTheDocument()
  })

  it('explains the change with both directions and the exact total', async () => {
    renderHistory()

    await screen.findByRole('table', { name: /monthly headroom over time/i })

    expect(screen.getByText(/£100\.00 more/i)).toBeInTheDocument()
    expect(screen.getByText(/wages/i)).toBeInTheDocument()
    expect(screen.getByText(/rent/i)).toBeInTheDocument()
  })

  it('never asserts a cause for a change', async () => {
    renderHistory()
    await screen.findByRole('table', { name: /monthly headroom over time/i })

    const bodyText = document.body.textContent ?? ''
    expect(bodyText).not.toMatch(/because/i)
    expect(bodyText).not.toMatch(/due to/i)
    expect(bodyText).not.toMatch(/caused by/i)
  })

  it('calls the first confirmed statement a baseline rather than a trend', async () => {
    getHistory.mockResolvedValue(
      ok(
        historyResponse({
          total: 1,
          snapshots: [snapshot('2026-08-01', '1500.00', '2450.00', '950.00')],
          series: [seriesPoint('2026-08-01', '1500.00')],
          latest_change: {
            is_baseline: true,
            previous_period: null,
            current_period: '2026-08-01',
            monthly_headroom_change: null,
            increases: [],
            decreases: [],
            warnings: ['no_comparable_period'],
          },
        }),
      ),
    )

    renderHistory()

    expect(await screen.findByText(/starting point/i)).toBeInTheDocument()
    const bodyText = document.body.textContent ?? ''
    expect(bodyText).not.toMatch(/increased|decreased/i)
  })

  it('shows a negative headroom as a shortfall without confusing formatting', async () => {
    getHistory.mockResolvedValue(
      ok(
        historyResponse({
          total: 1,
          snapshots: [snapshot('2026-08-01', '-180.00', '900.00', '1080.00')],
          series: [{ ...seriesPoint('2026-08-01', '-180.00'), result_code: 'shortfall' }],
          latest_change: null,
        }),
      ),
    )

    renderHistory()

    expect((await screen.findAllByText('-£180.00')).length).toBeGreaterThan(0)
    expect(document.body.textContent).not.toMatch(/£-180/)
  })

  it('lists every confirmed record including two for the same period', async () => {
    getHistory.mockResolvedValue(
      ok(
        historyResponse({
          total: 2,
          snapshots: [
            snapshot('2026-08-01', '1600.00', '2600.00', '1000.00'),
            { ...snapshot('2026-08-01', '1500.00', '2450.00', '950.00'), snapshot_id: 'snap-older' },
          ],
          series: [seriesPoint('2026-08-01', '1600.00')],
        }),
      ),
    )

    renderHistory()

    const records = await screen.findByRole('table', { name: /every confirmed record/i })
    expect(within(records).getAllByRole('row')).toHaveLength(3)
  })

  it('pages through history without losing the change explanation', async () => {
    // More records than fit on one page, so paging controls are warranted.
    getHistory.mockResolvedValue(ok(historyResponse({ total: 20, limit: 12, offset: 0 })))
    renderHistory()
    await screen.findByRole('table', { name: /monthly headroom over time/i })

    getHistory.mockResolvedValue(ok(historyResponse({ total: 20, limit: 12, offset: 12 })))
    await userEvent.click(screen.getByRole('button', { name: /older/i }))

    expect(await screen.findByText(/£100\.00 more/i)).toBeInTheDocument()
  })

  it('reports a failure without losing the customer', async () => {
    getHistory.mockResolvedValue({
      data: undefined,
      error: { detail: 'unavailable' },
      request: new Request('http://localhost/history'),
      response: new Response(null, { status: 503 }),
    } as never)

    renderHistory()

    expect(await screen.findByText(/can.t reach/i)).toBeInTheDocument()
  })
})
