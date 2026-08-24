import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import { Overview } from './Overview'
import {
  getOverviewOverviewGet,
  requestPersonalizedExplanationOverviewPersonalizedExplanationPost,
} from '@/api/generated'

vi.mock('@/api/generated', () => ({
  getOverviewOverviewGet: vi.fn(),
  requestPersonalizedExplanationOverviewPersonalizedExplanationPost: vi.fn(),
}))

function renderWithQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <Overview />
    </QueryClientProvider>,
  )
  return { ...rendered, queryClient }
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
const mockedRequestExplanation = vi.mocked(
  requestPersonalizedExplanationOverviewPersonalizedExplanationPost,
)

beforeEach(() => {
  mockedGetOverview.mockReset()
  mockedRequestExplanation.mockReset()
})

describe('Overview', () => {
  it('keeps deterministic content usable while optional wording is pending', async () => {
    mockedGetOverview.mockResolvedValue({
      data: {
        customer_id: 'c1',
        snapshot_id: '00000000-0000-0000-0000-000000000001',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-01T09:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '2450.00',
        normalized_monthly_outgoings: '1950.00',
        monthly_headroom: '500.00',
        result_code: 'surplus',
        warnings: [],
        income_entries: [],
        outgoing_entries: [],
        resilience: emptyResilience(),
        difficulty: {
          result_code: 'no_difficulty_identified',
          title: '',
          explanation: '',
          shortfall: null,
          protected_monthly_outgoings: '0.00',
          warnings: [],
          support_routes: [],
        },
        deterministic_explanation:
          'Reported monthly income is £2,450.00 and reported monthly outgoings are £1,950.00, leaving £500.00 of monthly headroom.',
        personalized_explanation: null,
      },
      error: undefined,
      request: new Request('http://localhost/overview'),
      response: new Response(null, { status: 200 }),
    } as never)
    mockedRequestExplanation.mockReturnValue(new Promise(() => {}) as never)

    renderWithQueryClient()
    await userEvent.click(await screen.findByRole('button', { name: /explain this more simply/i }))

    expect(screen.getByText(/reported monthly income is £2,450.00/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /creating optional wording/i })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent(/creating optional wording/i)
  })

  it('renders accepted wording as text rather than markup', async () => {
    mockedGetOverview.mockResolvedValue({
      data: {
        customer_id: 'c1',
        snapshot_id: '00000000-0000-0000-0000-000000000001',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-01T09:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '2450.00',
        normalized_monthly_outgoings: '1950.00',
        monthly_headroom: '500.00',
        result_code: 'surplus',
        warnings: [],
        income_entries: [],
        outgoing_entries: [],
        resilience: emptyResilience(),
        difficulty: {
          result_code: 'no_difficulty_identified',
          title: '',
          explanation: '',
          shortfall: null,
          protected_monthly_outgoings: '0.00',
          warnings: [],
          support_routes: [],
        },
        deterministic_explanation: 'Your deterministic explanation remains available.',
        personalized_explanation: null,
      },
      error: undefined,
      request: new Request('http://localhost/overview'),
      response: new Response(null, { status: 200 }),
    } as never)
    mockedRequestExplanation.mockResolvedValue({
      data: {
        snapshot_id: '00000000-0000-0000-0000-000000000001',
        text: '<strong>Your reported figures leave £500.00.</strong>',
        outcome: 'generated',
        deployment: 'guidance-v1',
        prompt_version: 'guidance-prompt-v1',
        schema_version: 'guidance-schema-v1',
        created_at: '2026-08-24T10:30:00Z',
      },
      error: undefined,
      request: new Request('http://localhost/overview/personalized-explanation'),
      response: new Response(null, { status: 200 }),
    } as never)

    renderWithQueryClient()
    await userEvent.click(await screen.findByRole('button', { name: /explain this more simply/i }))

    expect(await screen.findByText('<strong>Your reported figures leave £500.00.</strong>')).toBeInTheDocument()
    expect(document.querySelector('strong')).not.toBeInTheDocument()
    expect(screen.getByText(/your deterministic explanation remains available/i)).toBeInTheDocument()
  })

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

  it('announces exact shortfall support without treating flexible costs as spare money', async () => {
    mockedGetOverview.mockResolvedValue({
      data: {
        customer_id: 'c1',
        statement_period: '2026-08-01',
        confirmed_at: '2026-08-01T09:00:00Z',
        calculation_policy_version: 'normalization-policy-v1',
        normalized_monthly_income: '1000.00',
        normalized_monthly_outgoings: '1000.01',
        monthly_headroom: '-0.01',
        result_code: 'shortfall',
        warnings: [],
        income_entries: [],
        outgoing_entries: [],
        resilience: emptyResilience(),
        difficulty: {
          result_code: 'reported_shortfall',
          title: 'Reported outgoings are above income',
          explanation: 'The information reported shows an exact monthly shortfall of £0.01. Every reported living cost remains part of this result, including costs whose amount may vary.',
          shortfall: '0.01',
          protected_monthly_outgoings: '700.00',
          warnings: ['reported_shortfall'],
          support_routes: [
            {
              code: 'review_information',
              label: 'Review your information',
              description: 'Check what you reported.',
              url: '/statement',
              external: false,
            },
            {
              code: 'contact_ophelos',
              label: 'Contact Ophelos support',
              description: 'Talk to our support team placeholder.',
              url: 'mailto:support@example.ophelos.com',
              external: false,
            },
            {
              code: 'moneyhelper_debt_advice',
              label: 'Find free independent debt advice',
              description: 'Use the official locator.',
              url: 'https://www.moneyhelper.org.uk/en/money-troubles/dealing-with-debt/debt-advice-locator',
              external: true,
            },
          ],
        },
      },
      error: undefined,
    } as never)

    renderWithQueryClient()

    const result = (await screen.findByText('Reported outgoings are above income')).closest('[role="status"]')
    expect(result).not.toBeNull()
    expect(result).toHaveTextContent(/exact monthly shortfall of £0.01/i)
    expect(screen.getByRole('link', { name: /free independent debt advice/i })).toHaveAttribute('target', '_blank')
    expect(document.body.textContent).not.toMatch(/disposable|failed affordability|must pay/i)
  })

  it('ignores wording that arrives after the overview moves to a newer snapshot', async () => {
    const firstOverview = {
      customer_id: 'c1',
      snapshot_id: '00000000-0000-0000-0000-000000000001',
      statement_period: '2026-08-01',
      confirmed_at: '2026-08-01T09:00:00Z',
      calculation_policy_version: 'normalization-policy-v1',
      normalized_monthly_income: '2450.00',
      normalized_monthly_outgoings: '1950.00',
      monthly_headroom: '500.00',
      result_code: 'surplus',
      warnings: [],
      income_entries: [],
      outgoing_entries: [],
      resilience: emptyResilience(),
      difficulty: null,
      deterministic_explanation: 'The first snapshot leaves £500.00 of monthly headroom.',
      personalized_explanation: null,
    }
    const newerOverview = {
      ...firstOverview,
      snapshot_id: '00000000-0000-0000-0000-000000000002',
      normalized_monthly_outgoings: '2050.00',
      monthly_headroom: '400.00',
      deterministic_explanation: 'The corrected snapshot leaves £400.00 of monthly headroom.',
    }
    mockedGetOverview.mockResolvedValue({ data: firstOverview } as never)
    let resolveExplanation: (value: unknown) => void = () => undefined
    mockedRequestExplanation.mockReturnValue(
      new Promise((resolve) => {
        resolveExplanation = resolve
      }) as never,
    )

    const { queryClient } = renderWithQueryClient()
    await userEvent.click(await screen.findByRole('button', { name: /explain this more simply/i }))
    act(() => queryClient.setQueryData(['overview'], newerOverview))
    expect(await screen.findByText(/corrected snapshot leaves £400.00/i)).toBeInTheDocument()

    await act(async () => {
      resolveExplanation({
        data: {
          snapshot_id: firstOverview.snapshot_id,
          text: 'Late wording for the first snapshot.',
          outcome: 'generated',
          deployment: 'guidance-v1',
          prompt_version: 'guidance-prompt-v1',
          schema_version: 'guidance-schema-v1',
          created_at: '2026-08-24T10:30:00Z',
        },
      })
    })

    expect(screen.queryByText('Late wording for the first snapshot.')).not.toBeInTheDocument()
    expect(screen.getByText(/corrected snapshot leaves £400.00/i)).toBeInTheDocument()
  })
})
