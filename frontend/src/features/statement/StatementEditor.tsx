import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, Info, Plus, Trash2 } from 'lucide-react'

import {
  previewFinancialStatementFinancialStatementPreviewPost,
  retrieveFinancialStatementFinancialStatementGet,
  updateFinancialStatementFinancialStatementPut,
} from '@/api/generated'
import type {
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
import { FREQUENCIES, formatFrequency, formatGbp, formatPeriod } from '@/lib/format'

type FieldError = { field: string; code: string; message: string }

type EntryDraft = {
  entryId: string
  description: string
  amount: string
  frequency: string
  normalizedMonthlyAmount: string | null
}

type ResilienceDraft = {
  accessible_savings: string
  protected_reserve: string
  current_account_balance: string
  known_arrears: string
}

type ChangeDraft = EntryDraft & { kind: string }

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
  return {
    entryId: entry.entry_id,
    description: entry.description,
    amount: entry.original_amount,
    frequency: entry.original_frequency,
    normalizedMonthlyAmount: entry.normalized_monthly_amount,
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
  return entries.map((entry) => ({
    entry_id: entry.entryId,
    description: entry.description,
    amount: entry.amount,
    frequency: entry.frequency,
  }))
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

        {Number(preview.normalized_monthly_irregular_costs) > 0 && (
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
                  <li key={warning}>{warning}</li>
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
  const [version, setVersion] = useState<number | null>(null)
  const [errors, setErrors] = useState<FieldError[]>([])
  const [summaryMessage, setSummaryMessage] = useState<string | null>(null)
  const [conflictMessage, setConflictMessage] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [preview, setPreview] = useState<StatementPreviewResponse | null>(null)
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

  const activeDraft = draft ?? (query.data ? toDraft(query.data) : null)
  const activeVersion = version ?? query.data?.version ?? null

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
      setDraft(toDraft(data))
      setVersion(data.version)
      setPreview(null)
      setStatus('Your statement was saved.')
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
      <Alert variant="destructive" className="mx-auto w-full max-w-3xl">
        <AlertTriangle />
        <AlertTitle>We can&apos;t reach the server right now</AlertTitle>
        <AlertDescription>Your information hasn&apos;t been lost - please try again in a moment.</AlertDescription>
      </Alert>
    )
  }

  const update = (patch: Partial<Draft>) => {
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

      {status && (
        <p role="status" className="text-sm text-muted-foreground">
          {status}
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
    </div>
  )
}
