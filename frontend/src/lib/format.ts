const periodFormatter = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' })

export const FREQUENCIES = [
  'weekly',
  'fortnightly',
  'four_weekly',
  'monthly',
  'quarterly',
  'annual',
] as const

type DecimalParts = {
  negative: boolean
  integer: string
  fraction: string
}

function decimalParts(amount: string): DecimalParts {
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(amount.trim())
  if (!match) throw new Error(`Invalid decimal amount: ${amount}`)

  const integer = match[2].replace(/^0+(?=\d)/, '')
  const fraction = match[3] ?? ''
  const isZero = /^0+$/.test(integer) && (fraction === '' || /^0+$/.test(fraction))
  return { negative: match[1] === '-' && !isZero, integer, fraction }
}

export function formatGbp(amount: string): string {
  const parts = decimalParts(amount)
  if (parts.fraction.length > 2) throw new Error(`GBP amount has more than two decimal places: ${amount}`)

  const groupedInteger = parts.integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const fraction = parts.fraction.padEnd(2, '0')
  return `${parts.negative ? '-' : ''}£${groupedInteger}.${fraction}`
}

export function compareMoney(left: string, right: string): -1 | 0 | 1 {
  const leftParts = decimalParts(left)
  const rightParts = decimalParts(right)

  if (leftParts.negative !== rightParts.negative) return leftParts.negative ? -1 : 1

  const fractionLength = Math.max(leftParts.fraction.length, rightParts.fraction.length)
  const integerLength = Math.max(leftParts.integer.length, rightParts.integer.length)
  const leftMagnitude = `${leftParts.integer.padStart(integerLength, '0')}${leftParts.fraction.padEnd(fractionLength, '0')}`
  const rightMagnitude = `${rightParts.integer.padStart(integerLength, '0')}${rightParts.fraction.padEnd(fractionLength, '0')}`

  if (leftMagnitude === rightMagnitude) return 0
  const magnitudeResult = leftMagnitude > rightMagnitude ? 1 : -1
  return leftParts.negative ? (magnitudeResult * -1) as -1 | 1 : magnitudeResult
}

export function magnitudeOfMoney(amount: string): string {
  return amount.trim().replace(/^[+-]/, '')
}

export function formatFrequency(frequency: string): string {
  return frequency.replace('_', '-')
}

export function formatPeriod(statementPeriod: string): string {
  return periodFormatter.format(new Date(`${statementPeriod}T00:00:00Z`))
}
