import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  listDemoPresetsDemoPresetsGet,
  resetDemoDemoResetPost,
} from '@/api/generated'
import { DemoPresetPicker } from './DemoPresetPicker'

vi.mock('@/api/generated', () => ({
  listDemoPresetsDemoPresetsGet: vi.fn(),
  resetDemoDemoResetPost: vi.fn(),
}))

const listPresets = vi.mocked(listDemoPresetsDemoPresetsGet)
const resetDemo = vi.mocked(resetDemoDemoResetPost)

function renderPicker() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <DemoPresetPicker />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  listPresets.mockResolvedValue({
    data: {
      presets: [
        {
          code: 'zero_income',
          label: 'Zero income',
          description: 'No income is reported while protected living costs continue.',
          fictional: true,
        },
      ],
    },
    error: undefined,
  } as never)
})

describe('DemoPresetPicker', () => {
  it('warns before replacing fictional data and loads only after confirmation', async () => {
    resetDemo.mockResolvedValue({
      data: { preset: 'zero_income', message: 'Fictional demo data loaded.' },
      error: undefined,
    } as never)
    renderPicker()

    await screen.findByRole('option', { name: 'Zero income' })
    await userEvent.selectOptions(screen.getByLabelText(/demonstration preset/i), 'zero_income')

    expect(screen.getByRole('alert')).toHaveTextContent(/fictional demo data will be reset/i)
    expect(resetDemo).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: /load zero income/i }))

    expect(resetDemo).toHaveBeenCalledWith({
      body: { preset: 'zero_income', confirmed_reset: true },
    })
    expect(await screen.findByRole('status')).toHaveTextContent(/fictional demo data loaded/i)
  })

  it('can cancel a pending reset without changing data', async () => {
    renderPicker()

    await screen.findByRole('option', { name: 'Zero income' })
    await userEvent.selectOptions(screen.getByLabelText(/demonstration preset/i), 'zero_income')
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(resetDemo).not.toHaveBeenCalled()
  })
})
