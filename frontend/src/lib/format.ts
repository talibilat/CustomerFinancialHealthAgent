const gbpFormatter = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
})

const periodFormatter = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' })

export const FREQUENCIES = [
  'weekly',
  'fortnightly',
  'four_weekly',
  'monthly',
  'quarterly',
  'annual',
] as const

export function formatGbp(amount: string): string {
  return gbpFormatter.format(Number(amount))
}

export function formatFrequency(frequency: string): string {
  return frequency.replace('_', '-')
}

export function formatPeriod(statementPeriod: string): string {
  return periodFormatter.format(new Date(`${statementPeriod}T00:00:00Z`))
}
