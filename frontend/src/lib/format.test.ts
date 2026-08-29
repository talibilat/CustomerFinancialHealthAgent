import { describe, expect, it } from 'vitest'

import { compareMoney, formatGbp, magnitudeOfMoney } from './format'

describe('formatGbp', () => {
  it('formats exact decimal strings without converting them to binary floating point', () => {
    expect(formatGbp('9007199254740993.01')).toBe('£9,007,199,254,740,993.01')
    expect(formatGbp('-0.01')).toBe('-£0.01')
    expect(formatGbp('0')).toBe('£0.00')
  })
})

describe('money string helpers', () => {
  it('compares signs and returns magnitudes without using Number', () => {
    expect(compareMoney('0.01', '0.00')).toBe(1)
    expect(compareMoney('-0.01', '0.00')).toBe(-1)
    expect(compareMoney('-0.00', '0.00')).toBe(0)
    expect(magnitudeOfMoney('-9007199254740993.01')).toBe('9007199254740993.01')
  })
})
