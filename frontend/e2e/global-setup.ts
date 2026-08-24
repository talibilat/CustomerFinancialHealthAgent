import { expect, request } from '@playwright/test'

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? 'http://localhost:8000'

export default async function waitForApplicationReadiness() {
  const api = await request.newContext()
  try {
    await expect
      .poll(
        async () => {
          try {
            const response = await api.get(`${apiBaseUrl}/health/ready`)
            return response.status()
          } catch {
            return 0
          }
        },
        {
          message: 'backend readiness endpoint should return 200 before browser tests start',
          timeout: 120_000,
          intervals: [100, 250, 500, 1_000],
        },
      )
      .toBe(200)
  } finally {
    await api.dispose()
  }
}
