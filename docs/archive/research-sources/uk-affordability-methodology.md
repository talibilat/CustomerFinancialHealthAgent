# UK affordability and financial-health research

## Purpose and scope

This note identifies a defensible product methodology for assessing a UK customer's reported ability to sustain a debt repayment.
It is based on primary FCA and Money and Pensions Service sources current on 21 August 2026.
It is product research, not legal advice, and the exact rules that apply depend on Ophelos's regulated role and the product or agreement involved.

For debt collection and repayment arrangements, FCA CONC 7 is the closest regulatory benchmark.
CONC 5.2A concerns lending creditworthiness assessments, so it is useful supporting evidence for the meaning and information requirements of affordability rather than a claim that a collections feature performs a lender's statutory assessment.
CONC 8.5 applies to debt counselling firms that prepare financial statements and repayment offers for lenders, but its accuracy, sustainability, and verification principles are also useful design benchmarks.

## The defensible core

Affordability is not merely whether a payment fits beneath a percentage of income.
Under [CONC 7.3.5B to 7.3.5F](https://handbook.fca.org.uk/handbook/conc7/conc7s3), a repayment arrangement must be sustainable, an arrangement is unlikely to be sustainable if it prevents payment of priority debts and essential living expenses, and an income and expenditure assessment must be objective and based on sufficiently detailed information.
The same guidance allows firms to have regard to Standard Financial Statement spending guidelines and expects clear written policies for when and how assessments are made.

[CONC 5.2A.10R to 5.2A.12R](https://handbook.fca.org.uk/handbook/conc5/conc5s6) separates credit risk from affordability risk and asks whether repayments can be made when due over the life of the agreement without further borrowing, without missing contractual or statutory obligations, and without a significant adverse impact on the customer's financial situation.
This is a stronger and more customer-centred test than asking only whether a repayment is mathematically possible this month.

The product should therefore expose two distinct concepts:

- **Reported monthly headroom** is arithmetic based on the supplied snapshot.
- **Repayment sustainability** is a cautious interpretation of whether that headroom protects essential living costs, priority obligations, and a basic ability to absorb normal variation.

A defensible arithmetic basis is:

`reported headroom = regular net income - priority commitments - essential living costs - other contractual commitments - reasonable flexible living costs`

`headroom after proposal = reported headroom - proposed repayment`

The ordering matters.
Debt repayment should not displace priority commitments or essential living costs.
[CONC 7.3.5G](https://handbook.fca.org.uk/handbook/conc7/conc7s3) expressly gives no, reduced, or token payments as examples of forbearance where paying existing debts would prevent a customer meeting priority debts or essential living expenses.
[CONC 7.3.9R to 7.3.10R](https://handbook.fca.org.uk/handbook/conc7/conc7s3) also prohibits pressuring a customer into an unaffordable lump-sum payment, an unreasonably short repayment period, selling property, or raising funds through further borrowing.

## Expense treatment

[CONC 5.2A.18G](https://handbook.fca.org.uk/handbook/conc5/conc5s6) describes non-discretionary expenditure broadly.
It includes priority debts, essential living expenses, spending that is hard to reduce while maintaining a basic quality of life, contractual and statutory payment obligations, and costs paid for other people in the household.

[CONC 7.3.5C](https://handbook.fca.org.uk/handbook/conc7/conc7s3) identifies mortgage, rent, council tax, food, and utilities as examples of priority debts and essential living expenses, but explicitly says the list is not exhaustive.
[CONC 8.5.3G](https://handbook.fca.org.uk/handbook/conc8/conc8s5) adds taxes, fines, child support, and debts whose non-payment could cause loss of essential goods or services, repossession, or eviction.
It also makes essentiality contextual, giving telecommunications for a disabled customer as an example.

The model should distinguish at least:

- Priority and essential commitments, such as housing, council tax, food, utilities, child maintenance, and essential secured or hire-purchase payments.
- Other contractual commitments, including existing credit repayments.
- Reasonable flexible living costs, which are variable but not automatically disposable.
- An explicit contingency or savings amount where the customer reports one, rather than silently treating every remaining pound as repayable.

The [Standard Financial Statement Code of Conduct](https://standard-financial-statement.maps.org.uk/en/apply-to-use-the-sfs/sfs-code-of-conduct) confirms that its spending guidelines cover only three flexible-spending areas, are intended for over-indebted customers, adjust for household composition, and are updated at least annually using household expenditure and inflation data.
The detailed current spending guidelines are controlled materials available to SFS members and should not be copied, invented, or represented as implemented by this take-home.
The public SFS structure can inform category design, while a production system should use the licensed, current guidance or an approved equivalent.

## What monthly income and outgoings can establish

Given sufficiently complete and current inputs, the product can deterministically establish:

- The reported surplus or deficit before a proposed repayment.
- The reported buffer after a proposed repayment.
- Whether the proposal would mathematically intrude on reported essential or priority spending.
- Which input categories and amounts caused the result.
- How the reported position changed between snapshots.
- Scenario outcomes when the customer changes the proposed repayment or corrects an input.

These outputs should be described as based on reported information, not as facts about the customer's complete financial circumstances.

## What a monthly snapshot cannot establish

A single income and expenditure snapshot cannot, by itself, establish:

- That the inputs are complete, accurate, or independently verified.
- Whether income is volatile, seasonal, shared, or likely to fall.
- Whether essential costs are irregular, understated, temporarily reduced, or likely to rise.
- Whether annual and non-monthly costs have been converted realistically.
- The customer's household composition, dependants, or obligations to other people unless collected.
- Whether a low flexible-spending amount reflects a sustainable choice or current deprivation.
- Available savings, assets, emergency resilience, arrears, total balances, interest, payment duration, or consequences of missed payments unless collected.
- Vulnerability, accessibility needs, or a life event unless the customer discloses it or another reliable signal exists.
- Causation from a historical trend.

These limitations follow from the FCA's information requirements.
[CONC 5.2A.15R to 5.2A.20R](https://handbook.fca.org.uk/handbook/conc5/conc5s6) requires reasonable estimates of current income and non-discretionary expenditure, consideration of foreseeable income reductions and expenditure increases, evidence for favourable future changes, and an assessment proportionate to the individual's circumstances.
It warns that statistical expenditure data can be inappropriate where household composition, dependants, or indebtedness differ from the underlying sample.
[CONC 5.2A.23G](https://handbook.fca.org.uk/handbook/conc5/conc5s6) also warns that older information may need updating.

[CONC 8.5.1R and 8.5.4R](https://handbook.fca.org.uk/handbook/conc8/conc8s5) provides a useful stronger benchmark for a complete financial statement: it should be accurate, realistic, clear, and complete; the customer should confirm its accuracy; reasonable verification steps should be taken; and unusually high or low expenditure should prompt an explanation rather than automatic correction.

## Why fixed ratio thresholds are not defensible as the decision rule

The primary sources do not prescribe a universal debt-to-income, payment-to-income, or minimum-buffer percentage for these repayment arrangements.
Instead, [CONC 7.3.4B](https://handbook.fca.org.uk/handbook/conc7/conc7s3) requires consideration of the individual circumstances of the customer, and [CONC 7.3.5D to 7.3.5E](https://handbook.fca.org.uk/handbook/conc7/conc7s3) requires an objective assessment supported by sufficiently detailed information.
[CONC 5.2A.20R](https://handbook.fca.org.uk/handbook/conc5/conc5s6) likewise makes the scope and depth of assessment proportionate to each case.
[CONC 8.5.5G](https://handbook.fca.org.uk/handbook/conc8/conc8s5) says expenditure guidelines must still take account of individual circumstances.

A fixed ratio may be displayed as a descriptive metric or used as a review trigger, but it should not override the cash-flow and essential-needs test.
For example, two customers with the same repayment-to-income ratio may have materially different housing costs, dependants, disability-related costs, income volatility, and exposure to priority-debt consequences.

The take-home should not claim that a payment below an invented percentage is "affordable".
A more defensible deterministic classification is:

- **Not enough reported headroom** when the proposal exceeds reported headroom or essential and priority costs are already not covered.
- **Needs review** when information is incomplete, stale, volatile, unusually low or high, or the remaining buffer is zero or fragile.
- **Appears manageable from the information provided** when reported headroom covers the proposal with a positive disclosed buffer and no identified warning condition.

The last label should remain qualified because positive arithmetic is evidence, not proof, of sustainability over time.
No universal positive buffer should be presented as an FCA or SFS threshold.

## Fair treatment, vulnerability, and explanation

[CONC 7.3.4R to 7.3.4B](https://handbook.fca.org.uk/handbook/conc7/conc7s3) requires forbearance and due consideration for customers in or approaching arrears and requires the customer's individual circumstances to inform that treatment.
[CONC 7.3.5I to 7.3.5J](https://handbook.fca.org.uk/handbook/conc7/conc7s3) requires reasonable steps to keep forbearance appropriate, including reviews and responses to new information.
[CONC 7.3.7A](https://handbook.fca.org.uk/handbook/conc7/conc7s3) supports signposting to free, impartial money guidance or debt advice and, where possible, giving customers a record of the income and expenditure assessment that they can share.

The Consumer Duty requires more than a calculation.
[PRIN 2A.2](https://handbook.fca.org.uk/handbook/prin2a) requires firms to act in good faith, avoid foreseeable harm, and support customers in pursuing their financial objectives.
[PRIN 2A.5.3 to 2A.5.9](https://handbook.fca.org.uk/handbook/prin2a) requires communications to meet information needs, be likely to be understood, support properly informed decisions, be clear, fair, and not misleading, make key information prominent, and account for vulnerability and whether the firm is giving advice or information.
[PRIN 2A.6.2](https://handbook.fca.org.uk/handbook/prin2a) requires support journeys to meet the needs of customers with characteristics of vulnerability and include appropriate friction where needed to prevent harm.

The FCA's [FG21/1 vulnerable customer guidance](https://www.fca.org.uk/publications/finalised-guidance/guidance-firms-fair-treatment-vulnerable-customers) treats vulnerability as a spectrum and identifies health, life events, low financial resilience, and low capability as drivers.
It expects product design, service, communications, and monitoring to consider the needs and outcomes of vulnerable customers.

For this product, explainability should therefore mean:

- Lead with the answer, the proposed payment, and the resulting pounds-per-month buffer.
- Show the exact income and cost totals used, the calculation, and any missing or stale inputs.
- Use calm, non-judgmental language and avoid a credit-score-style label that implies a permanent personal trait.
- Explain that flexible living costs are still real needs and are not automatically available for debt repayment.
- Allow correction and scenario exploration before commitment.
- Avoid defaulting the customer into the highest mathematically possible payment.
- Offer a clear route to human support and free independent debt advice when essentials are uncovered, the position is worsening, or the customer says the proposal is not manageable.
- Preserve deterministic explanations even if an LLM later rewrites them into plain language.

An LLM-generated explanation should never change the calculation, classification, or recommended support route.
It should be grounded only in the structured result, visibly optional, validated against allowed facts, and replaced by a deterministic template on failure.
This is a product-control inference from the FCA's requirements that communications be clear, fair, not misleading, tailored, and likely to be understood.

## Research conclusion

The strongest take-home position is a deterministic, auditable cash-flow assessment based on reported household circumstances, with priority and essential needs protected before unsecured debt repayment.
It should use qualified outcomes, surface data quality and uncertainty, retain a positive disclosed buffer rather than maximizing collection, and invite review when the data cannot support a reliable conclusion.
Historical snapshots can show direction and prompt reassessment, but should not be presented as proof of causation or future affordability.
SFS concepts are credible category and process references, but current licensed spending figures should not be fabricated.
Fixed ratios can aid explanation or triage, but they are not a defensible substitute for individualized sustainability assessment.
