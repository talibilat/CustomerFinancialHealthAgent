import { QueryClient } from '@tanstack/react-query'

/**
 * The application's shared query defaults.
 *
 * Mutations here confirm snapshots, record corrections, and save scenarios.
 * A silent replay of any of those could duplicate history, so retrying them
 * automatically is disabled explicitly rather than left to a library default
 * that could change. A retry is the customer's decision, and the backend's
 * idempotency keys make a deliberate one safe.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        // A background refetch would replace an in-progress draft and discard
        // unsaved edits without warning.
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  })
}
