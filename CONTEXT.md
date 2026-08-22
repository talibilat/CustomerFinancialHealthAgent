# Customer Financial Health

This context describes the language used to explain a customer's reported financial position, resilience, repayment scenarios, and history.
It deliberately avoids claiming that the product provides financial advice or proves long-term affordability.

## Customer information

**Customer**:
A person using Ophelos who has reported income, outgoings, and existing repayment commitments.
_Avoid_: Debtor, account

**Financial statement**:
The customer's current editable collection of reported income, outgoings, existing repayment commitments, and optional resilience information for one statement period.
_Avoid_: Budget, assessment

**Statement period**:
The calendar month that a financial statement describes, regardless of when the customer confirms it.
_Avoid_: Effective financial period, save month

**Income entry**:
A customer-reported receipt with an amount and frequency that contributes to monthly income.
_Avoid_: Salary, earnings

**Outgoing**:
A customer-reported living cost, bill, provision, or repayment with an amount and frequency that contributes to monthly outgoings.
_Avoid_: Expense, spending

**Existing repayment commitment**:
A recurring debt payment already included in the financial statement.
_Avoid_: Debt balance, repayment scenario

**Known arrears**:
An amount the customer reports as overdue, kept distinct from a recurring outgoing or an agreed repayment commitment.
_Avoid_: Existing repayment, debt balance

**Confirmed snapshot**:
An immutable historical record of a financial statement and the results calculated when the customer confirmed it.
_Avoid_: Saved draft, monthly record

**Effective snapshot**:
The confirmed snapshot that currently represents a statement period because it has not been superseded by a correction.
_Avoid_: Latest record, current month

**Correction**:
A new confirmed snapshot that supersedes an earlier snapshot without altering or deleting the earlier record.
_Avoid_: Edit, overwrite

## Financial position

**Monthly headroom**:
The amount remaining after normalized monthly outgoings are subtracted from normalized monthly income.
_Avoid_: Disposable income, available repayment money

**Protected monthly buffer**:
The amount the customer wants to keep available each month for unexpected or changing costs.
_Avoid_: Required buffer, FCA threshold

**Accessible savings**:
Money the customer reports as readily available, presented as resilience rather than recurring income.
_Avoid_: Available repayment money

**Protected reserve**:
The portion of accessible savings the customer wants to preserve for emergencies or future needs.
_Avoid_: Excess cash, repayable savings

**Financial resilience**:
The relationship between accessible savings, the protected reserve, and reported future provisions.
_Avoid_: Affordability, net worth

## Repayment exploration

**Repayment scenario**:
A what-if comparison that changes one existing repayment or adds a hypothetical repayment without modifying its basis snapshot.
_Avoid_: Repayment recommendation, repayment plan, Ophelos repayment

**Basis snapshot**:
The confirmed snapshot whose reported values a repayment scenario compares against.
_Avoid_: Current statement, mutable baseline

**Scenario headroom**:
The monthly headroom that would remain if a repayment scenario applied.
_Avoid_: Approved payment capacity

## Classification

**Display category**:
A customer-friendly label such as Housing, Food and housekeeping, or Leisure and hobbies.
_Avoid_: Affordability category

**Outgoing treatment**:
One of four deterministic ways an outgoing participates in explanations: protected outgoing, existing credit commitment, flexible living cost, or protected future provision.
_Avoid_: Affordability category, AI category

**Protected outgoing**:
An essential living cost or priority commitment that is protected before exploring an unsecured repayment.
_Avoid_: Priority essential, disposable cost

**Existing credit commitment**:
An existing repayment commitment shown separately from other outgoings when explaining the customer's position.
_Avoid_: Repayment scenario, new repayment

**Flexible living cost**:
A genuine reported living cost whose amount may vary, without implying that it is unnecessary or available for repayment.
_Avoid_: Disposable spending, non-essential spending

**Protected future provision**:
A recurring amount the customer has chosen to set aside for known irregular costs, contingency, or a future need.
_Avoid_: Spare money, investment recommendation

**Classification suggestion**:
An unconfirmed category and treatment proposed by deterministic rules or Azure OpenAI.
_Avoid_: Classification

**Confirmed classification**:
The display category and outgoing treatment accepted or corrected by the customer.
_Avoid_: AI decision

**Customer classification preference**:
A customer-scoped rule created from a confirmed correction and reused for matching future entries.
_Avoid_: Global prompt update

## Results

**Current-position result**:
A deterministic description of whether reported monthly income is above, equal to, or below reported monthly outgoings.
_Avoid_: Financial-health score, approval

**Resilience result**:
A deterministic description of accessible savings relative to the customer's protected reserve.
_Avoid_: Affordability result

**Scenario result**:
A qualified deterministic description of whether a repayment scenario leaves enough reported headroom relative to the protected monthly buffer.
_Avoid_: Recommended repayment, affordability approval

**Deterministic explanation**:
A reproducible explanation generated from calculated amounts, result codes, warnings, and historical changes without an LLM.
_Avoid_: AI explanation

**Personalized explanation**:
Optional customer-friendly wording generated by Azure OpenAI from approved deterministic facts.
_Avoid_: Financial advice, assessment

**Support route**:
A deterministic action shown for a warning condition, such as reviewing information, contacting Ophelos support, or finding free independent debt advice.
_Avoid_: AI recommendation
