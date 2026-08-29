import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Info, Plus, Trash2 } from 'lucide-react'

import {
  confirmFinancialStatementFinancialStatementConfirmPost,
  previewFinancialStatementFinancialStatementPreviewPost,
  retrieveFinancialStatementFinancialStatementGet,
  updateFinancialStatementFinancialStatementPut,
} from '@/api/generated'
import type {
  ConfirmedSnapshotResponse,
  EditableStatementResponse,
  StatementEntryOut,
  StatementPreviewResponse,
} from '@/api/generated'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { LoadError } from '@/components/LoadError'
import { compareMoney, FREQUENCIES, formatFrequency, formatGbp, formatPeriod } from '@/lib/format'
import { warningCopy } from '@/lib/warning-copy'

type FieldError = { field: string; code: string; message: string }

type EntryDraft = {
  entryId: string
  description: string
  amount: string
  frequency: string
  normalizedMonthlyAmount: string | null
  classification?: ClassificationDraft
}

type ResilienceDraft = {
  accessible_savings: string
  protected_reserve: string
  current_account_balance: string
  known_arrears: string
}

type ClassificationDraft = {
  displayCategory: string
  outgoingTreatment: string
  requiresConfirmation: boolean
  reasonCode: string | null
  /** Only a classification the customer touched is sent back. */
  touched: boolean
  remember: boolean
  suggestion?: ClassificationSuggestionDraft
}

type ClassificationSuggestionDraft = {
  displayCategory: string
  outgoingTreatment: string
  confidence: string
  reason: string
  requiresClarification: boolean
}

type ChangeDraft = EntryDraft & { kind: string }

// Customer-facing labels. Treatment wording deliberately never implies that a
// reported cost is spare money.
const DISPLAY_CATEGORIES = [
  { value: 'housing', label: 'Housing' },
  { value: 'council_tax_and_priority_bills', label: 'Council tax and priority bills' },
  { value: 'utilities', label: 'Utilities' },
  { value: 'food_and_housekeeping', label: 'Food and housekeeping' },
  { value: 'transport', label: 'Transport' },
  { value: 'health_and_care', label: 'Health and care' },
  { value: 'children_and_dependants', label: 'Children and dependants' },
  { value: 'communications', label: 'Communications' },
  { value: 'insurance', label: 'Insurance' },
  { value: 'existing_debt_repayments', label: 'Existing debt repayments' },
  { value: 'leisure_and_hobbies', label: 'Leisure and hobbies' },
  { value: 'savings_and_future_provisions', label: 'Savings and future provisions' },
  { value: 'other', label: 'Other' },
] as const

const OUTGOING_TREATMENTS = [
  { value: 'protected_outgoing', label: 'Protected outgoing' },
  { value: 'existing_credit_commitment', label: 'Existing credit commitment' },
  { value: 'flexible_living_cost', label: 'Flexible living cost' },
  { value: 'protected_future_provision', label: 'Protected future provision' },
] as const

type Draft = {
  income: EntryDraft[]
  outgoings: EntryDraft[]
  commitments: EntryDraft[]
  irregularCosts: EntryDraft[]
  futureProvisions: EntryDraft[]
  expectedChanges: ChangeDraft[]
  resilience: ResilienceDraft
}

type EntryCollection =
  | 'income_entries'
  | 'outgoing_entries'
  | 'repayment_commitments'
  | 'looking_ahead.irregular_costs'
  | 'looking_ahead.protected_future_provisions'
  | 'looking_ahead.expected_changes'

type StoredDraft = {
  statementPeriod: string
  version: number
  draft: Draft
}

const DRAFT_STORAGE_KEY = 'financial-statement-unsaved-draft'

function isStoredDraft(value: unknown): value is StoredDraft {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<StoredDraft>
  const draft = candidate.draft as Partial<Draft> | undefined
  return (
    typeof candidate.statementPeriod === 'string' &&
    typeof candidate.version === 'number' &&
    typeof draft === 'object' &&
    draft !== null &&
    Array.isArray(draft.income) &&
    Array.isArray(draft.outgoings) &&
    Array.isArray(draft.commitments) &&
    Array.isArray(draft.irregularCosts) &&
    Array.isArray(draft.futureProvisions) &&
    Array.isArray(draft.expectedChanges) &&
    typeof draft.resilience === 'object' &&
    draft.resilience !== null
  )
}

function loadStoredDraft(statementPeriod: string, version: number | undefined): StoredDraft | null {
  if (version === undefined) return null
  try {
    const raw = sessionStorage.getItem(DRAFT_STORAGE_KEY)
    const stored: unknown = raw ? JSON.parse(raw) : null
    return isStoredDraft(stored) &&
      stored.statementPeriod === statementPeriod &&
      stored.version === version
      ? stored
      : null
  } catch {
    return null
  }
}

const EXPECTED_CHANGE_KINDS = [
  { value: 'income_increase', label: 'Income going up' },
  { value: 'income_decrease', label: 'Income going down' },
  { value: 'expenditure_increase', label: 'A cost going up' },
  { value: 'expenditure_decrease', label: 'A cost going down' },
] as const

/** Field paths use dots; DOM ids cannot, so the two are kept in step here. */
function domId(fieldPath: string): string {
  return `field-${fieldPath.replace(/\./g, '-')}`
}

function toDraftEntry(entry: StatementEntryOut): EntryDraft {
  const wireClassification = entry.classification
  return {
    entryId: entry.entry_id,
    description: entry.description,
    amount: entry.original_amount,
    frequency: entry.original_frequency,
    normalizedMonthlyAmount: entry.normalized_monthly_amount,
    classification: wireClassification
      ? {
          displayCategory: wireClassification.display_category ?? '',
          outgoingTreatment: wireClassification.outgoing_treatment ?? '',
          requiresConfirmation: wireClassification.requires_confirmation,
          reasonCode: wireClassification.reason_code ?? null,
          touched: false,
          remember: false,
          suggestion: wireClassification.suggestion
            ? {
                displayCategory: wireClassification.suggestion.display_category,
                outgoingTreatment: wireClassification.suggestion.outgoing_treatment,
                confidence: wireClassification.suggestion.confidence,
                reason: wireClassification.suggestion.reason,
                requiresClarification: wireClassification.suggestion.requires_clarification,
              }
            : undefined,
        }
      : undefined,
  }
}

function blankEntry(): EntryDraft {
  return {
    entryId: `new-${Math.random().toString(36).slice(2, 10)}`,
    description: '',
    amount: '',
    frequency: 'monthly',
    normalizedMonthlyAmount: null,
  }
}

function toDraft(response: EditableStatementResponse): Draft {
  const { statement } = response
  return {
    income: statement.income_entries.map(toDraftEntry),
    outgoings: statement.outgoing_entries.map(toDraftEntry),
    commitments: statement.repayment_commitments.map(toDraftEntry),
    irregularCosts: statement.looking_ahead.irregular_costs.map(toDraftEntry),
    futureProvisions: statement.looking_ahead.protected_future_provisions.map(toDraftEntry),
    expectedChanges: statement.looking_ahead.expected_changes.map((change) => ({
      ...toDraftEntry(change),
      kind: change.kind,
    })),
    resilience: {
      accessible_savings: statement.resilience.accessible_savings ?? '',
      protected_reserve: statement.resilience.protected_reserve ?? '',
      current_account_balance: statement.resilience.current_account_balance ?? '',
      known_arrears: statement.resilience.known_arrears ?? '',
    },
  }
}

function toSubmittedEntries(entries: EntryDraft[]) {
  return entries.map((entry) => {
    const base = {
      entry_id: entry.entryId,
      description: entry.description,
      amount: entry.amount,
      frequency: entry.frequency,
    }
    // Only a classification the customer actually settled is sent, so a
    // deterministic match is never silently recorded as their decision.
    const classification = entry.classification
    if (!classification?.touched || !classification.displayCategory || !classification.outgoingTreatment) {
      return base
    }
    return {
      ...base,
      classification: {
        display_category: classification.displayCategory,
        outgoing_treatment: classification.outgoingTreatment,
        remember: classification.remember,
      },
    }
  })
}

/** An omitted optional amount stays omitted rather than becoming a zero. */
function optionalAmount(value: string): string | null {
  return value.trim() === '' ? null : value
}

function toSubmission(draft: Draft, statementPeriod: string) {
  return {
    statement_period: statementPeriod,
    currency: 'GBP',
    income_entries: toSubmittedEntries(draft.income),
    outgoing_entries: toSubmittedEntries(draft.outgoings),
    repayment_commitments: toSubmittedEntries(draft.commitments),
    resilience: {
      accessible_savings: optionalAmount(draft.resilience.accessible_savings),
      protected_reserve: optionalAmount(draft.resilience.protected_reserve),
      current_account_balance: optionalAmount(draft.resilience.current_account_balance),
      known_arrears: optionalAmount(draft.resilience.known_arrears),
    },
    looking_ahead: {
      irregular_costs: toSubmittedEntries(draft.irregularCosts),
      protected_future_provisions: toSubmittedEntries(draft.futureProvisions),
      expected_changes: draft.expectedChanges.map((change) => ({
        entry_id: change.entryId,
        description: change.description,
        kind: change.kind,
        amount: change.amount,
        frequency: change.frequency,
      })),
    },
  }
}

function errorFor(errors: FieldError[], fieldPath: string): FieldError | undefined {
  return errors.find((error) => error.field === fieldPath)
}

function entriesFor(draft: Draft, collection: EntryCollection): EntryDraft[] {
  const collections: Record<EntryCollection, EntryDraft[]> = {
    income_entries: draft.income,
    outgoing_entries: draft.outgoings,
    repayment_commitments: draft.commitments,
    'looking_ahead.irregular_costs': draft.irregularCosts,
    'looking_ahead.protected_future_provisions': draft.futureProvisions,
    'looking_ahead.expected_changes': draft.expectedChanges,
  }
  return collections[collection]
}

/** Convert server index paths to stable entry paths before rows can be removed or reordered. */
function stableFieldPath(field: string, draft: Draft): string {
  const collections: EntryCollection[] = [
    'income_entries',
    'outgoing_entries',
    'repayment_commitments',
    'looking_ahead.irregular_costs',
    'looking_ahead.protected_future_provisions',
    'looking_ahead.expected_changes',
  ]
  const collection = collections.find((candidate) => field.startsWith(`${candidate}.`))
  if (!collection) return field

  const remainder = field.slice(collection.length + 1)
  const [indexText, ...tail] = remainder.split('.')
  if (!/^\d+$/.test(indexText)) return field
  const entry = entriesFor(draft, collection)[Number(indexText)]
  if (!entry) return field
  return `${collection}.${entry.entryId}.${tail.join('.')}`
}

function stableErrors(errors: FieldError[], draft: Draft): FieldError[] {
  return errors.map((error) => ({ ...error, field: stableFieldPath(error.field, draft) }))
}

function generatedValidationErrors(detail: unknown, draft: Draft): FieldError[] {
  if (!Array.isArray(detail)) return []
  return stableErrors(
    detail.flatMap((issue) => {
      if (!issue || typeof issue !== 'object') return []
      const candidate = issue as { loc?: unknown; msg?: unknown; type?: unknown }
      if (!Array.isArray(candidate.loc) || typeof candidate.msg !== 'string') return []
      const field = candidate.loc
        .filter((part, index) => !(index === 0 && part === 'body'))
        .map(String)
        .join('.')
      if (!field) return []
      return [{ field, code: typeof candidate.type === 'string' ? candidate.type : 'invalid', message: candidate.msg }]
    }),
    draft,
  )
}

function FieldMessage({ error }: { error: FieldError | undefined }) {
  if (!error) return null
  return (
    <p className="mt-1 text-sm font-medium text-destructive" id={`${domId(error.field)}-error`}>
      {error.message}
    </p>
  )
}

function EntryRow({
  noun,
  fieldPrefix,
  entry,
  errors,
  onChange,
  onRemove,
}: {
  noun: string
  fieldPrefix: string
  entry: EntryDraft
  errors: FieldError[]
  onChange: (next: EntryDraft) => void
  onRemove: () => void
}) {
  const label = entry.description || 'New entry'
  const path = (field: string) => `${fieldPrefix}.${entry.entryId}.${field}`
  const amountError = errorFor(errors, path('amount'))
  const frequencyError = errorFor(errors, path('frequency'))
  const descriptionError = errorFor(errors, path('description'))

  return (
    <div role="group" aria-label={`${noun}: ${label}`} className="rounded-lg border p-3">
      <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
        <div>
          <label className="text-sm text-muted-foreground" htmlFor={domId(path('description'))}>
            Description
          </label>
          <Input
            id={domId(path('description'))}
            type="text"
            aria-label={`${label} description`}
            aria-invalid={descriptionError ? true : undefined}
            aria-describedby={descriptionError ? `${domId(path('description'))}-error` : undefined}
            value={entry.description}
            onChange={(event) => onChange({ ...entry, description: event.target.value })}
          />
          <FieldMessage error={descriptionError} />
        </div>

        <div>
          <label className="text-sm text-muted-foreground" htmlFor={domId(path('amount'))}>
            Amount (£)
          </label>
          <Input
            id={domId(path('amount'))}
            // Deliberately a text field: the backend owns the money rules, so an
            // unusable value reaches it and comes back as a field-specific error
            // instead of being silently discarded by the browser.
            type="text"
            inputMode="decimal"
            aria-label={`${label} amount`}
            aria-invalid={amountError ? true : undefined}
            aria-describedby={amountError ? `${domId(path('amount'))}-error` : undefined}
            value={entry.amount}
            onChange={(event) =>
              onChange({ ...entry, amount: event.target.value, normalizedMonthlyAmount: null })
            }
          />
          <FieldMessage error={amountError} />
        </div>

        <div>
          <label className="text-sm text-muted-foreground" htmlFor={domId(path('frequency'))}>
            Frequency
          </label>
          <select
            id={domId(path('frequency'))}
            aria-label={`${label} frequency`}
            aria-invalid={frequencyError ? true : undefined}
            aria-describedby={frequencyError ? `${domId(path('frequency'))}-error` : undefined}
            className="border-input bg-background h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs"
            value={entry.frequency}
            onChange={(event) =>
              onChange({ ...entry, frequency: event.target.value, normalizedMonthlyAmount: null })
            }
          >
            {FREQUENCIES.map((frequency) => (
              <option key={frequency} value={frequency}>
                {formatFrequency(frequency)}
              </option>
            ))}
          </select>
          <FieldMessage error={frequencyError} />
        </div>

        <Button type="button" variant="ghost" aria-label={`Remove ${label}`} onClick={onRemove}>
          <Trash2 aria-hidden="true" />
          <span className="sr-only sm:not-sr-only">Remove</span>
        </Button>
      </div>

      {entry.normalizedMonthlyAmount !== null && (
        <p className="mt-2 text-sm text-muted-foreground">
          {formatGbp(entry.amount)} ({formatFrequency(entry.frequency)}) normalizes to{' '}
          <span className="text-foreground">{formatGbp(entry.normalizedMonthlyAmount)} per month</span>
        </p>
      )}

      {entry.classification && (
        <ClassificationFields
          label={label}
          path={path}
          classification={entry.classification}
          errors={errors}
          onChange={(classification) => onChange({ ...entry, classification })}
        />
      )}
    </div>
  )
}

function ClassificationFields({
  label,
  path,
  classification,
  errors,
  onChange,
}: {
  label: string
  path: (field: string) => string
  classification: ClassificationDraft
  errors: FieldError[]
  onChange: (next: ClassificationDraft) => void
}) {
  const categoryPath = path('classification.display_category')
  const treatmentPath = path('classification.outgoing_treatment')
  const categoryError = errorFor(errors, categoryPath)
  const treatmentError = errorFor(errors, treatmentPath)
  const unresolved = classification.requiresConfirmation && !classification.touched
  const suggestion = classification.suggestion
  const suggestedCategory = suggestion
    ? DISPLAY_CATEGORIES.find((category) => category.value === suggestion.displayCategory)?.label
    : undefined
  const suggestedTreatment = suggestion
    ? OUTGOING_TREATMENTS.find((treatment) => treatment.value === suggestion.outgoingTreatment)?.label
    : undefined
  const confidence = suggestion ? Math.round(Number(suggestion.confidence) * 100) : null

  return (
    <div className="mt-3 border-t pt-3">
      {unresolved && (
        <p className="mb-2 text-sm font-medium">
          Tell us what this was for. We will not guess on your behalf.
        </p>
      )}

      {unresolved && suggestion && suggestedCategory && suggestedTreatment && (
        <div className="mb-3 rounded-lg border bg-muted/40 p-3 text-sm">
          <p className="font-medium">Optional suggestion</p>
          <p className="mt-1">
            {suggestedCategory} and {suggestedTreatment}
            {confidence !== null ? ` (${confidence}% confidence)` : ''}
          </p>
          <p className="mt-1 text-muted-foreground">{suggestion.reason}</p>
          {suggestion.requiresClarification && (
            <p className="mt-1 text-muted-foreground">
              This description could mean different things, so please check it carefully.
            </p>
          )}
          <p className="mt-1 text-muted-foreground">
            This is only a suggestion. Nothing changes unless you choose it.
          </p>
          <Button
            type="button"
            variant="outline"
            className="mt-2"
            aria-label={`Use this suggestion for ${label}`}
            onClick={() =>
              onChange({
                ...classification,
                displayCategory: suggestion.displayCategory,
                outgoingTreatment: suggestion.outgoingTreatment,
                touched: true,
              })
            }
          >
            Use this suggestion
          </Button>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="text-sm text-muted-foreground" htmlFor={domId(categoryPath)}>
            Category
          </label>
          <select
            id={domId(categoryPath)}
            aria-label={`${label} category`}
            aria-invalid={categoryError ? true : undefined}
            aria-describedby={categoryError ? `${domId(categoryPath)}-error` : undefined}
            className="border-input bg-background h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs"
            value={classification.displayCategory}
            onChange={(event) =>
              // The treatment is deliberately left alone: whether a cost is
              // essential depends on the customer's circumstances, not its label.
              onChange({ ...classification, displayCategory: event.target.value, touched: true })
            }
          >
            <option value="">Choose a category</option>
            {DISPLAY_CATEGORIES.map((category) => (
              <option key={category.value} value={category.value}>
                {category.label}
              </option>
            ))}
          </select>
          <FieldMessage error={categoryError} />
        </div>

        <div>
          <label className="text-sm text-muted-foreground" htmlFor={domId(treatmentPath)}>
            How this is treated
          </label>
          <select
            id={domId(treatmentPath)}
            aria-label={`${label} treatment`}
            aria-invalid={treatmentError ? true : undefined}
            aria-describedby={treatmentError ? `${domId(treatmentPath)}-error` : undefined}
            className="border-input bg-background h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs"
            value={classification.outgoingTreatment}
            onChange={(event) =>
              onChange({ ...classification, outgoingTreatment: event.target.value, touched: true })
            }
          >
            <option value="">Choose how this is treated</option>
            {OUTGOING_TREATMENTS.map((treatment) => (
              <option key={treatment.value} value={treatment.value}>
                {treatment.label}
              </option>
            ))}
          </select>
          <FieldMessage error={treatmentError} />
        </div>
      </div>

      {classification.touched && (
        <label className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            aria-label={`Remember this for ${label}`}
            checked={classification.remember}
            onChange={(event) => onChange({ ...classification, remember: event.target.checked })}
          />
          Remember this for future statements
        </label>
      )}

      <p className="mt-2 text-sm text-muted-foreground">
        A flexible living cost is still a real cost you reported. It is never treated as money
        available for repayment.
      </p>
    </div>
  )
}

function EntrySection({
  title, description, noun, addLabel, fieldPrefix, entries, errors, onChange,
}: {
  title: string
  description?: string
  noun: string
  addLabel: string
  fieldPrefix: string
  entries: EntryDraft[]
  errors: FieldError[]
  onChange: (next: EntryDraft[]) => void
}) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="font-medium">{title}</h3>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>

      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing reported yet.</p>
      ) : (
        entries.map((entry, index) => (
          <EntryRow
            key={entry.entryId}
            noun={noun}
            fieldPrefix={fieldPrefix}
            entry={entry}
            errors={errors}
            onChange={(next) => onChange(entries.map((e, i) => (i === index ? next : e)))}
            onRemove={() => onChange(entries.filter((_, i) => i !== index))}
          />
        ))
      )}

      <Button type="button" variant="outline" onClick={() => onChange([...entries, blankEntry()])}>
        <Plus aria-hidden="true" />
        {addLabel}
      </Button>
    </section>
  )
}

function ExpectedChangeSection({
  entries,
  errors,
  onChange,
}: {
  entries: ChangeDraft[]
  errors: FieldError[]
  onChange: (next: ChangeDraft[]) => void
}) {
  const fieldPrefix = 'looking_ahead.expected_changes'

  return (
    <section className="space-y-3">
      <div>
        <h3 className="font-medium">Expected changes</h3>
        <p className="text-sm text-muted-foreground">
          Optional. Something you already know is changing soon. This is recorded for context and
          does not change the position for this statement period.
        </p>
      </div>

      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing reported yet.</p>
      ) : (
        entries.map((change, index) => {
          const label = change.description || 'New entry'
          const path = (field: string) => `${fieldPrefix}.${change.entryId}.${field}`
          const kindError = errorFor(errors, path('kind'))
          const replace = (next: ChangeDraft) => onChange(entries.map((c, i) => (i === index ? next : c)))

          return (
            <div
              key={change.entryId}
              role="group"
              aria-label={`Expected change: ${label}`}
              className="space-y-3 rounded-lg border p-3"
            >
              <div>
                <label className="text-sm text-muted-foreground" htmlFor={domId(path('kind'))}>
                  What is changing
                </label>
                <select
                  id={domId(path('kind'))}
                  aria-label={`${label} kind`}
                  aria-invalid={kindError ? true : undefined}
                  aria-describedby={kindError ? `${domId(path('kind'))}-error` : undefined}
                  className="border-input bg-background h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs"
                  value={change.kind}
                  onChange={(event) => replace({ ...change, kind: event.target.value })}
                >
                  {EXPECTED_CHANGE_KINDS.map((kind) => (
                    <option key={kind.value} value={kind.value}>
                      {kind.label}
                    </option>
                  ))}
                </select>
                <FieldMessage error={kindError} />
              </div>

              <EntryRow
                noun="Change detail"
                fieldPrefix={fieldPrefix}
                entry={change}
                errors={errors}
                onChange={(next) => replace({ ...next, kind: change.kind })}
                onRemove={() => onChange(entries.filter((_, i) => i !== index))}
              />
            </div>
          )
        })
      )}

      <Button
        type="button"
        variant="outline"
        onClick={() =>
          onChange([...entries, { ...blankEntry(), kind: EXPECTED_CHANGE_KINDS[0].value }])
        }
      >
        <Plus aria-hidden="true" />
        Add an expected change
      </Button>
    </section>
  )
}

function OptionalAmountField({
  label, fieldPath, value, errors, onChange, hint,
}: {
  label: string
  fieldPath: string
  value: string
  errors: FieldError[]
  onChange: (next: string) => void
  hint?: string
}) {
  const error = errorFor(errors, fieldPath)
  const hintId = hint ? `${domId(fieldPath)}-hint` : undefined
  const errorId = error ? `${domId(fieldPath)}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined
  return (
    <div>
      <label className="text-sm text-muted-foreground" htmlFor={domId(fieldPath)}>
        {label}
      </label>
      <Input
        id={domId(fieldPath)}
        type="text"
        inputMode="decimal"
        aria-label={label}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint && <p className="mt-1 text-sm text-muted-foreground" id={hintId}>{hint}</p>}
      <FieldMessage error={error} />
    </div>
  )
}

function ErrorSummary({
  message,
  errors,
  summaryRef,
}: {
  message: string
  errors: FieldError[]
  summaryRef: React.RefObject<HTMLDivElement | null>
}) {
  return (
    <div
      ref={summaryRef}
      role="alert"
      aria-label="There is a problem"
      tabIndex={-1}
      className="rounded-lg border border-destructive/50 p-4"
    >
      <h2 className="font-medium">There is a problem</h2>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {errors.map((error) => (
          <li key={error.field}>
            <a className="underline" href={`#${domId(error.field)}`}>
              {error.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

function PreviewPanel({ preview }: { preview: StatementPreviewResponse }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>Preview</CardDescription>
        <CardTitle className="text-lg">Your position if you save this</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm text-muted-foreground">Monthly headroom</p>
          <p className="text-3xl font-semibold tracking-tight">{formatGbp(preview.monthly_headroom)}</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-sm text-muted-foreground">Normalized monthly income</p>
            <p className="text-xl font-medium">{formatGbp(preview.normalized_monthly_income)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Normalized monthly outgoings</p>
            <p className="text-xl font-medium">{formatGbp(preview.normalized_monthly_outgoings)}</p>
          </div>
        </div>

        {compareMoney(preview.normalized_monthly_irregular_costs, '0') > 0 && (
          <p className="text-sm text-muted-foreground">
            Irregular costs set aside {formatGbp(preview.normalized_monthly_irregular_costs)} a month.
            This is shown separately and is not part of the monthly headroom above.
          </p>
        )}

        <p className="text-sm text-muted-foreground">
          This is a preview. Nothing has been saved and your confirmed history has not changed. It
          reflects the information reported for this statement period and is not a proof of long-term
          affordability.
        </p>

        {preview.warnings.length > 0 && (
          <Alert>
            <Info />
            <AlertTitle>Limitations</AlertTitle>
            <AlertDescription>
              <ul>
                {preview.warnings.map((warning) => (
                  <li key={warning}>{warningCopy(warning)}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}

export function StatementEditor({ statementPeriod }: { statementPeriod: string }) {
  const [draft, setDraft] = useState<Draft | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [version, setVersion] = useState<number | null>(null)
  const [errors, setErrors] = useState<FieldError[]>([])
  const [summaryMessage, setSummaryMessage] = useState<string | null>(null)
  const [conflictMessage, setConflictMessage] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [preview, setPreview] = useState<StatementPreviewResponse | null>(null)
  const [checkedInformation, setCheckedInformation] = useState(false)
  const [confirmed, setConfirmed] = useState<ConfirmedSnapshotResponse | null>(null)
  const [confirmConflict, setConfirmConflict] = useState<string | null>(null)
  // One reference per previewed statement, so a retry or a double click is
  // recognised as the same confirmation rather than a second one.
  const idempotencyKey = useRef<string>('')
  const summaryRef = useRef<HTMLDivElement | null>(null)

  const query = useQuery({
    queryKey: ['financial-statement', statementPeriod],
    queryFn: async () => {
      const result = await retrieveFinancialStatementFinancialStatementGet({
        query: { statement_period: statementPeriod },
      })
      if (result.error || !result.data) throw new Error('statement_unavailable')
      return result.data as EditableStatementResponse
    },
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const storedDraft = loadStoredDraft(statementPeriod, query.data?.version)
  const activeDraft = draft ?? storedDraft?.draft ?? (query.data ? toDraft(query.data) : null)
  const activeVersion = version ?? storedDraft?.version ?? query.data?.version ?? null
  const visibleStatus =
    status ?? (draft === null && storedDraft ? 'We restored your unsaved changes from this browser tab.' : null)

  useEffect(() => {
    if (!draft || !isDirty || activeVersion === null) return
    const stored: StoredDraft = { statementPeriod, version: activeVersion, draft }
    sessionStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(stored))
  }, [activeVersion, draft, isDirty, statementPeriod])

  // A rejected submission must never discard what the customer typed, so the
  // draft is only ever replaced by a fresh retrieval or an accepted save.
  function applyRejection(detail: unknown, status: number) {
    const body = (detail ?? {}) as { code?: string; message?: string; errors?: FieldError[]; current_version?: number }
    if (status === 409) {
      setConflictMessage(body.message ?? 'This statement changed. Refresh to see the current version.')
      return
    }
    const rejectedDraft = activeDraft as Draft
    const fieldErrors = Array.isArray(detail)
      ? generatedValidationErrors(detail, rejectedDraft)
      : stableErrors(body.errors ?? [], rejectedDraft)
    setErrors(fieldErrors)
    setSummaryMessage(body.message ?? 'Nothing was saved. Check the highlighted fields and try again.')
  }

  const previewMutation = useMutation({
    mutationFn: async () => {
      const result = await previewFinancialStatementFinancialStatementPreviewPost({
        body: toSubmission(activeDraft as Draft, statementPeriod) as never,
      })
      if (result.error || !result.data) {
        applyRejection((result.error as { detail?: unknown })?.detail, result.response?.status ?? 0)
        throw new Error('preview_rejected')
      }
      return result.data as StatementPreviewResponse
    },
    onMutate: () => {
      setErrors([])
      setSummaryMessage(null)
      setStatus(null)
    },
    onSuccess: (data) => {
      setPreview(data)
      idempotencyKey.current = `confirm-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
      setCheckedInformation(false)
      setConfirmed(null)
      setConfirmConflict(null)
      setStatus('Preview updated. Nothing has been saved.')
    },
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      const result = await updateFinancialStatementFinancialStatementPut({
        body: { ...toSubmission(activeDraft as Draft, statementPeriod), expected_version: activeVersion } as never,
      })
      if (result.error || !result.data) {
        applyRejection((result.error as { detail?: unknown })?.detail, result.response?.status ?? 0)
        throw new Error('save_rejected')
      }
      return result.data as EditableStatementResponse
    },
    onMutate: () => {
      setErrors([])
      setSummaryMessage(null)
      setConflictMessage(null)
      setStatus(null)
    },
    onSuccess: (data) => {
      sessionStorage.removeItem(DRAFT_STORAGE_KEY)
      setIsDirty(false)
      setDraft(toDraft(data))
      setVersion(data.version)
      setPreview(null)
      setStatus('Your statement was saved.')
    },
  })

  const confirmMutation = useMutation({
    mutationFn: async () => {
      const result = await confirmFinancialStatementFinancialStatementConfirmPost({
        body: {
          ...toSubmission(activeDraft as Draft, statementPeriod),
          expected_version: version,
          checked_information: true,
        } as never,
        headers: { 'Idempotency-Key': idempotencyKey.current },
      })
      if (result.error || !result.data) {
        const detail = (result.error as { detail?: unknown })?.detail
        const body = (detail ?? {}) as { code?: string; message?: string; errors?: FieldError[] }
        if (body.code === 'statement_version_conflict' || body.code === 'classifications_unresolved') {
          setConfirmConflict(body.message ?? 'This statement changed. Preview it again before confirming.')
        } else {
          applyRejection(detail, result.response?.status ?? 0)
        }
        throw new Error('confirm_rejected')
      }
      return result.data as ConfirmedSnapshotResponse
    },
    onMutate: () => {
      setConfirmConflict(null)
      setStatus(null)
    },
    onSuccess: (data) => {
      sessionStorage.removeItem(DRAFT_STORAGE_KEY)
      setIsDirty(false)
      setConfirmed(data)
      setStatus('Your statement was saved to your history.')
    },
  })

  useEffect(() => {
    if (summaryMessage) summaryRef.current?.focus()
  }, [summaryMessage])

  if (query.isLoading) {
    return (
      <Card className="mx-auto w-full max-w-3xl">
        <CardHeader>
          <Skeleton className="h-5 w-48" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </CardContent>
        <p role="status" className="sr-only">
          Loading your financial statement&hellip;
        </p>
      </Card>
    )
  }

  if (query.isError || !activeDraft) {
    return (
      <LoadError
        subject="information"
        className="mx-auto w-full max-w-3xl"
        retrying={query.isFetching}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const update = (patch: Partial<Draft>) => {
    setIsDirty(true)
    setDraft({ ...activeDraft, ...patch })
    setPreview(null)
    setStatus(null)
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      {summaryMessage && (
        <ErrorSummary message={summaryMessage} errors={errors} summaryRef={summaryRef} />
      )}

      {conflictMessage && (
        <Alert>
          <Info />
          <AlertTitle>This statement changed somewhere else</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{conflictMessage}</p>
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                const refreshed = await query.refetch()
                if (!refreshed.data) return
                setDraft(toDraft(refreshed.data))
                sessionStorage.removeItem(DRAFT_STORAGE_KEY)
                setIsDirty(false)
                setVersion(refreshed.data.version)
                setErrors([])
                setSummaryMessage(null)
                setConflictMessage(null)
                setPreview(null)
              }}
            >
              Refresh this statement
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {visibleStatus && (
        <p role="status" className="text-sm text-muted-foreground">
          {visibleStatus}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardDescription>{formatPeriod(statementPeriod)}</CardDescription>
          <CardTitle className="text-lg">Your financial statement</CardTitle>
          <CardDescription>
            Change anything that no longer matches your circumstances. Nothing is saved to your
            history until you confirm it.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-8">
          <EntrySection
            title="Income"
            noun="Income"
            addLabel="Add an income entry"
            fieldPrefix="income_entries"
            entries={activeDraft.income}
            errors={errors}
            onChange={(income) => update({ income })}
          />

          <Separator />

          <EntrySection
            title="Outgoings"
            noun="Outgoing"
            addLabel="Add an outgoing"
            fieldPrefix="outgoing_entries"
            entries={activeDraft.outgoings}
            errors={errors}
            onChange={(outgoings) => update({ outgoings })}
          />

          <Separator />

          <EntrySection
            title="Existing repayment commitments"
            description="Repayments you already make. These count towards your monthly outgoings and are shown separately."
            noun="Repayment commitment"
            addLabel="Add a repayment commitment"
            fieldPrefix="repayment_commitments"
            entries={activeDraft.commitments}
            errors={errors}
            onChange={(commitments) => update({ commitments })}
          />

          <Separator />

          <section className="space-y-3">
            <div>
              <h3 className="font-medium">Financial resilience</h3>
              <p className="text-sm text-muted-foreground">
                Optional. Leaving these blank creates a limitation rather than an assumed value. These
                figures never become monthly income.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <OptionalAmountField
                label="Accessible savings"
                fieldPath="resilience.accessible_savings"
                value={activeDraft.resilience.accessible_savings}
                errors={errors}
                onChange={(accessible_savings) =>
                  update({ resilience: { ...activeDraft.resilience, accessible_savings } })
                }
              />
              <OptionalAmountField
                label="Protected reserve"
                fieldPath="resilience.protected_reserve"
                value={activeDraft.resilience.protected_reserve}
                errors={errors}
                onChange={(protected_reserve) =>
                  update({ resilience: { ...activeDraft.resilience, protected_reserve } })
                }
              />
              <OptionalAmountField
                label="Current-account balance"
                hint="Enter a negative amount if you are overdrawn."
                fieldPath="resilience.current_account_balance"
                value={activeDraft.resilience.current_account_balance}
                errors={errors}
                onChange={(current_account_balance) =>
                  update({ resilience: { ...activeDraft.resilience, current_account_balance } })
                }
              />
              <OptionalAmountField
                label="Known arrears"
                fieldPath="resilience.known_arrears"
                value={activeDraft.resilience.known_arrears}
                errors={errors}
                onChange={(known_arrears) =>
                  update({ resilience: { ...activeDraft.resilience, known_arrears } })
                }
              />
            </div>
          </section>

          <Separator />

          <EntrySection
            title="Irregular costs"
            description="Optional. Costs that arrive once or twice a year are spread into a monthly provision and shown separately from your monthly outgoings."
            noun="Irregular cost"
            addLabel="Add an irregular cost"
            fieldPrefix="looking_ahead.irregular_costs"
            entries={activeDraft.irregularCosts}
            errors={errors}
            onChange={(irregularCosts) => update({ irregularCosts })}
          />

          <Separator />

          <EntrySection
            title="Protected future provisions"
            description="Optional. Amounts you set aside for a known future need."
            noun="Protected future provision"
            addLabel="Add a future provision"
            fieldPrefix="looking_ahead.protected_future_provisions"
            entries={activeDraft.futureProvisions}
            errors={errors}
            onChange={(futureProvisions) => update({ futureProvisions })}
          />

          <Separator />

          <ExpectedChangeSection
            entries={activeDraft.expectedChanges}
            errors={errors}
            onChange={(expectedChanges) => update({ expectedChanges })}
          />

          <Separator />

          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              onClick={() => previewMutation.mutate()}
              disabled={previewMutation.isPending}
            >
              Preview my position
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              Save my statement
            </Button>
          </div>
        </CardContent>
      </Card>

      {preview && <PreviewPanel preview={preview} />}

      {preview && (
        <ConfirmationPanel
          preview={preview}
          checked={checkedInformation}
          onCheckedChange={setCheckedInformation}
          onConfirm={() => confirmMutation.mutate()}
          pending={confirmMutation.isPending}
          conflictMessage={confirmConflict}
          confirmed={confirmed}
        />
      )}
    </div>
  )
}

function ConfirmationPanel({
  preview,
  checked,
  onCheckedChange,
  onConfirm,
  pending,
  conflictMessage,
  confirmed,
}: {
  preview: StatementPreviewResponse
  checked: boolean
  onCheckedChange: (next: boolean) => void
  onConfirm: () => void
  pending: boolean
  conflictMessage: string | null
  confirmed: ConfirmedSnapshotResponse | null
}) {
  const unresolved = (preview.unresolved_classifications ?? []).length > 0

  if (confirmed) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">This statement is saved to your history</CardTitle>
          <CardDescription>
            Confirmed {new Date(confirmed.confirmed_at).toLocaleString('en-GB')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <p className="text-sm text-muted-foreground">Monthly headroom</p>
            <p className="text-3xl font-semibold tracking-tight">
              {formatGbp(confirmed.monthly_headroom)}
            </p>
          </div>
          <p className="text-sm text-muted-foreground">
            This record does not change. If something here turns out to be wrong, corrections
            create a new snapshot and the original stays in your history.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Save this to your history</CardTitle>
        <CardDescription>
          Once saved, this record does not change. Corrections create a new snapshot later.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-3 sm:grid-cols-3">
          <div>
            <dt className="text-sm text-muted-foreground">Income</dt>
            <dd className="text-lg font-medium">
              {formatGbp(preview.normalized_monthly_income)}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Outgoings</dt>
            <dd className="text-lg font-medium">
              {formatGbp(preview.normalized_monthly_outgoings)}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Monthly headroom</dt>
            <dd className="text-lg font-medium">{formatGbp(preview.monthly_headroom)}</dd>
          </div>
        </dl>

        {unresolved && (
          <Alert>
            <Info />
            <AlertTitle>Not ready yet</AlertTitle>
            <AlertDescription>
              Tell us what each outgoing was for before saving this to your history.
            </AlertDescription>
          </Alert>
        )}

        {conflictMessage && (
          <Alert>
            <Info />
            <AlertTitle>This statement changed</AlertTitle>
            <AlertDescription>{conflictMessage}</AlertDescription>
          </Alert>
        )}

        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            aria-label="I have checked this information"
            checked={checked}
            onChange={(event) => onCheckedChange(event.target.checked)}
          />
          <span>
            I have checked this information and believe it reflects my circumstances. Ophelos has
            not independently checked it.
          </span>
        </label>

        <Button type="button" disabled={!checked || unresolved || pending} onClick={onConfirm}>
          Confirm this statement
        </Button>
      </CardContent>
    </Card>
  )
}
