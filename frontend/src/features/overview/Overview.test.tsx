import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import { Overview } from './Overview'
import { getOverviewOverviewGet } from '@/api/generated'

vi.mock('@/api/generated', () => ({
  getOverviewOverviewGet: vi.fn(),
}))

function renderWithQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <Overview />
    </QueryClientProvider>,
  )
}

function emptyResilience() {
  return {
    accessible_savings: null,
    protected_reserve: null,
    current_account_balance: null,
    known_arrears: null,
    savings_above_reserve: null,
    reserve_gap: null,
    result_code: null,
    warnings: ['resilience_info_missing'],
  }
}

const mockedGetOverview = vi.mocked(getOverviewOverviewGet)

beforeEach(() => {
  mockedGetOverview.mockReset()
})

describe('Overview', () => {
  it('shows a loading state before data arrives', () => {
    mockedGetOverview.mockReturnValue(new Promise(() => {}) as never)

    renderWithQueryClient()

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('shows a recoverable message when the backend is unavailable', async () => {
    mockedGetOverview.mockResolvedValue({
      data: undefined,
      error: { detail: 'unavailable' },
      request: new Request('http://localhost/overview'),
      response: new Response(null, { status: 503 }),
    } as never)

    renderWithQueryClient()

    expect(await screen.findByText(/can.t reach/i)).toBeInTheDocument()
  })

  it('leads with normalized monthly income, outgoings, and exact headroom in GBP', async () => {
    mockedGetOverview.mockResolvedValue({
      data: {
        customer_id: 'c1',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-01T09:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '2450.00',
        normalized_monthly_outgoings: '1195.00',
        monthly_headroom: '1255.00',
        result_code: 'surplus',
        warnings: [],
        income_entries: [
          { original_amount: '2450.00', original_frequency: 'monthly', normalized_monthly_amount: '2450.00' },
        ],
        outgoing_entries: [
          { original_amount: '950.00', original_frequency: 'monthly', normalized_monthly_amount: '950.00' },
        ],
        resilience: emptyResilience(),
      },
      error: undefined,
      request: new Request('http://localhost/overview'),
      response: new Response(null, { status: 200 }),
    } as never)

    renderWithQueryClient()

    expect(await screen.findByText('£2,450.00')).toBeInTheDocument()
    expect(screen.getByText('£1,195.00')).toBeInTheDocument()
    expect(screen.getByText('£1,255.00')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /review how this was calculated/i }))

    expect(screen.getByText(/normalization-policy-v1/)).toBeInTheDocument()
  })

  it('never describes a surplus as proof of long-term affordability', async () => {
    mockedGetOverview.mockResolvedValue({
      data: {
        customer_id: 'c1',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-01T09:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '2450.00',
        normalized_monthly_outgoings: '1195.00',
        monthly_headroom: '1255.00',
        result_code: 'surplus',
        warnings: [],
        income_entries: [],
        outgoing_entries: [],
        resilience: emptyResilience(),
      },
      error: undefined,
      request: new Request('http://localhost/overview'),
      response: new Response(null, { status: 200 }),
    } as never)

    renderWithQueryClient()

    await screen.findByText('£1,255.00')

    const bodyText = document.body.textContent ?? ''
    expect(bodyText).not.toMatch(/you can afford/i)
    expect(bodyText).not.toMatch(/\bhealthy\b/i)
    expect(bodyText).not.toMatch(/\bapproved\b/i)
    expect(bodyText).toMatch(/not a proof of long-term affordability/i)
  })

  it('shows resilience below the protected reserve without changing the displayed headroom', async () => {
    mockedGetOverview.mockResolvedValue({
      data: {
        customer_id: 'c1',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-01T09:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '2450.00',
        normalized_monthly_outgoings: '1518.75',
        monthly_headroom: '931.25',
        result_code: 'surplus',
        warnings: [],
        income_entries: [],
        outgoing_entries: [],
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
      },
      error: undefined,
      request: new Request('http://localhost/overview'),
      response: new Response(null, { status: 200 }),
    } as never)

    renderWithQueryClient()

    expect(await screen.findByText('£931.25')).toBeInTheDocument()
    expect(screen.getByText('£300.00')).toBeInTheDocument()
    expect(screen.getByText('£1,000.00')).toBeInTheDocument()
    expect(screen.getByText('-£45.30')).toBeInTheDocument()
    expect(screen.getByText('£700.00')).toBeInTheDocument()
    expect(screen.getByText(/below.*protected reserve/i)).toBeInTheDocument()

    const bodyText = document.body.textContent ?? ''
    expect(bodyText).not.toMatch(/net worth/i)
    expect(bodyText).not.toMatch(/excess cash/i)
  })

  it('still shows reported balance and arrears when savings and reserve are missing', async () => {
    mockedGetOverview.mockResolvedValue({
      data: {
        customer_id: 'c1',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-01T09:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '2000.00',
        normalized_monthly_outgoings: '1500.00',
        monthly_headroom: '500.00',
        result_code: 'surplus',
        warnings: [],
        income_entries: [],
        outgoing_entries: [],
        resilience: {
          accessible_savings: null,
          protected_reserve: null,
          current_account_balance: '125.40',
          known_arrears: '640.00',
          savings_above_reserve: null,
          reserve_gap: null,
          result_code: null,
          warnings: ['resilience_info_missing'],
        },
      },
      error: undefined,
      request: new Request('http://localhost/overview'),
      response: new Response(null, { status: 200 }),
    } as never)

    renderWithQueryClient()

    expect(await screen.findByText('£500.00')).toBeInTheDocument()
    expect(screen.getByText('£125.40')).toBeInTheDocument()
    expect(screen.getByText('£640.00')).toBeInTheDocument()
  })

  it('announces the resilience limitation when information is missing', async () => {
    mockedGetOverview.mockResolvedValue({
      data: {
        customer_id: 'c1',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-01T09:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '2000.00',
        normalized_monthly_outgoings: '1500.00',
        monthly_headroom: '500.00',
        result_code: 'surplus',
        warnings: [],
        income_entries: [],
        outgoing_entries: [],
        resilience: emptyResilience(),
      },
      error: undefined,
      request: new Request('http://localhost/overview'),
      response: new Response(null, { status: 200 }),
    } as never)

    renderWithQueryClient()

    await screen.findByText('£500.00')

    expect(screen.getByText('resilience_info_missing')).toBeInTheDocument()
  })

  it('shows a limitation instead of blocking when resilience information is missing', async () => {
    mockedGetOverview.mockResolvedValue({
      data: {
        customer_id: 'c1',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-01T09:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '1000.00',
        normalized_monthly_outgoings: '200.00',
        monthly_headroom: '800.00',
        result_code: 'surplus',
        warnings: [],
        income_entries: [],
        outgoing_entries: [],
        resilience: emptyResilience(),
      },
      error: undefined,
      request: new Request('http://localhost/overview'),
      response: new Response(null, { status: 200 }),
    } as never)

    renderWithQueryClient()

    expect(await screen.findByText('£800.00')).toBeInTheDocument()
    expect(screen.getByText(/add accessible savings and a protected reserve/i)).toBeInTheDocument()
  })
})
