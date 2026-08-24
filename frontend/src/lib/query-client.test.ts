import { describe, expect, it } from 'vitest'

import { createQueryClient } from './query-client'

describe('query client defaults', () => {
  it('never automatically replays a failed mutation', () => {
    const defaults = createQueryClient().getDefaultOptions()

    // Confirming a statement, correcting a snapshot, and saving a scenario are
    // all non-idempotent from the browser's point of view: a silent replay
    // could duplicate history.
    expect(defaults.mutations?.retry).toBe(false)
  })

  it('retries reads a bounded number of times', () => {
    const defaults = createQueryClient().getDefaultOptions()

    expect(defaults.queries?.retry).toBe(1)
  })

  it('does not refetch on window focus, so unsaved edits survive', () => {
    const defaults = createQueryClient().getDefaultOptions()

    expect(defaults.queries?.refetchOnWindowFocus).toBe(false)
  })
})
