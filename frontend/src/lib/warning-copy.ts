const WARNING_COPY: Record<string, string> = {
  incomplete_information:
    'Income and outgoings have not both been reported, so the monthly position is incomplete.',
  zero_income:
    'No monthly income has been reported, so the result shows the full amount of reported monthly outgoings as a shortfall.',
  resilience_info_missing:
    'Accessible savings and a protected reserve have not both been provided, so a savings comparison is not available.',
  reported_shortfall:
    'Reported monthly outgoings are above reported monthly income for this statement period.',
  protected_outgoings_not_covered:
    'Reported monthly income does not cover all outgoings identified as protected.',
  protected_buffer_missing:
    'No protected monthly buffer has been provided, so this comparison cannot show how much room would remain above it.',
  no_reported_headroom_before_this_repayment:
    'The reported monthly position has no headroom before the repayment being explored.',
  no_headroom_left_after_this_repayment:
    'The repayment being explored would leave no reported monthly headroom.',
  looking_ahead_info_missing:
    'No irregular costs, future provisions, or expected changes have been reported for this statement period.',
  possible_irregular_cost_duplication:
    'An irregular cost may also appear in monthly outgoings, so review the entries before confirming.',
  no_comparable_period:
    'There is no earlier confirmed statement period available for this comparison.',
  change_decomposition_incomplete:
    'Some of the overall change cannot be matched to individual reported entries.',
}

const UNKNOWN_WARNING_COPY =
  'Some of the supporting information is limited, so treat this result as a guide based on what was reported.'

export function warningCopy(warning: string): string {
  return WARNING_COPY[warning] ?? UNKNOWN_WARNING_COPY
}
