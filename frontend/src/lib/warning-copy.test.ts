import { describe, expect, it } from 'vitest'

import { warningCopy } from './warning-copy'

describe('warningCopy', () => {
  it('turns every known internal warning identifier into calm customer copy', () => {
    const knownWarnings = [
      'incomplete_information',
      'zero_income',
      'resilience_info_missing',
      'reported_shortfall',
      'protected_outgoings_not_covered',
      'protected_buffer_missing',
      'no_reported_headroom_before_this_repayment',
      'no_headroom_left_after_this_repayment',
      'looking_ahead_info_missing',
      'possible_irregular_cost_duplication',
      'no_comparable_period',
      'change_decomposition_incomplete',
    ]

    for (const warning of knownWarnings) {
      const copy = warningCopy(warning)
      expect(copy).not.toBe(warning)
      expect(copy).not.toContain('_')
      expect(copy.length).toBeGreaterThan(20)
    }
  })

  it('uses safe generic copy for an unknown identifier', () => {
    expect(warningCopy('provider_internal_code')).toBe(
      'Some of the supporting information is limited, so treat this result as a guide based on what was reported.',
    )
  })
})
