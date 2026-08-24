import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info } from 'lucide-react'

import {
  listSavedScenariosRepaymentScenariosGet,
  previewRepaymentScenarioRepaymentScenarioPreviewPost,
  retrieveScenarioBasisRepaymentScenarioBasisGet,
  saveScenarioRepaymentScenariosPost,
} from '@/api/generated'
import type { SavedScenarioResponse, ScenarioResponse } from '@/api/generated'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { LoadError } from '@/components/LoadError'
import { formatGbp, formatPeriod } from '@/lib/format'

type FieldError = { field: string; code: string; message: string }

const MODES = [
  { value: 'additional', label: 'Paying something extra on top' },
  { value: 'change_existing', label: 'Changing a repayment I already make' },
] as const

// Deliberately qualified wording. None of these states says a repayment is
// affordable, and none of them recommends an amount.
const RESULT_WORDING: Record<string, string> = {
  not_enough_reported_headroom: 'Not enough reported headroom',
  may_leave_limited_room: 'May leave limited room',
  appears_manageable_from_the_information_provided:
    'Appears manageable from the information provided',
}

function errorFor(errors: FieldError[], field: string) {
  return errors.find((error) => error.field === field)
}

function FieldMessage({ error }: { error: FieldError | undefined }) {
  if (!error) return null
  return (
    <p className="mt-1 text-sm font-medium text-destructive" id={`scenario-${error.field}-error`}>
      {error.message}
    </p>
  )
}

function AmountField({
  id,
  label,
  value,
  onChange,
  errors,
  field,
}: {
  id: string
  label: string
  value: string
  onChange: (next: string) => void
  errors: FieldError[]
  field: string
}) {
  const error = errorFor(errors, field)
  return (
    <div>
      <label className="text-sm text-muted-foreground" htmlFor={id}>
        {label}
      </label>
      <Input
        id={id}
        type="text"
        inputMode="decimal"
        aria-label={label}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `scenario-${field}-error` : undefined}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <FieldMessage error={error} />
    </div>
  )
}

function ScenarioResultPanel({ result }: { result: ScenarioResponse }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>
          Compared with your confirmed {formatPeriod(result.basis_statement_period)} statement
        </CardDescription>
        <CardTitle className="text-lg">
          {RESULT_WORDING[result.result_code] ?? 'May leave limited room'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-4 sm:grid-cols-3">
          <div>
            <dt className="text-sm text-muted-foreground">Monthly headroom now</dt>
            <dd className="text-xl font-medium">{formatGbp(result.basis_monthly_headroom)}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Repayment considered</dt>
            <dd className="text-xl font-medium">{formatGbp(result.proposed_repayment)}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Headroom afterwards</dt>
            <dd className="text-3xl font-semibold tracking-tight">
              {formatGbp(result.scenario_headroom)}
            </dd>
          </div>
        </dl>

        <p className="text-sm text-muted-foreground">
          {result.replaced_repayment
            ? `${formatGbp(result.basis_monthly_headroom)} + ${formatGbp(result.replaced_repayment)} freed - ${formatGbp(result.proposed_repayment)} = ${formatGbp(result.scenario_headroom)}`
            : `${formatGbp(result.basis_monthly_headroom)} - ${formatGbp(result.proposed_repayment)} = ${formatGbp(result.scenario_headroom)}`}
        </p>

        {result.buffer_shortfall && (
          <p className="text-sm text-muted-foreground">
            That is {formatGbp(result.buffer_shortfall)} below the monthly buffer you set.
          </p>
        )}

        <p className="text-sm text-muted-foreground">
          Nothing here changes your statement, your history, or any agreement. It is a comparison
          based on what you reported, not advice about what to pay.
        </p>

        {result.warnings.length > 0 && (
          <Alert>
            <Info />
            <AlertTitle>Limitations</AlertTitle>
            <AlertDescription>
              <ul>
                {result.warnings.map((warning) => (
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

function SavedScenarioCard({ scenario }: { scenario: SavedScenarioResponse }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>
          Based on your confirmed {formatPeriod(scenario.basis_statement_period)} statement
        </CardDescription>
        <CardTitle className="text-lg">
          {RESULT_WORDING[scenario.result_code] ?? 'May leave limited room'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {scenario.basis_is_superseded && (
          <Alert>
            <Info />
            <AlertTitle>This basis statement was later corrected</AlertTitle>
            <AlertDescription>
              This saved scenario still uses the original statement and values. It has not been
              recalculated against the correction.
            </AlertDescription>
          </Alert>
        )}
        <dl className="grid gap-3 sm:grid-cols-3">
          <div>
            <dt className="text-sm text-muted-foreground">Headroom on its basis</dt>
            <dd className="font-medium">{formatGbp(scenario.basis_monthly_headroom)}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Repayment considered</dt>
            <dd className="font-medium">{formatGbp(scenario.proposed_repayment)} repayment</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Result on that basis</dt>
            <dd className="font-medium">
              {formatGbp(scenario.scenario_headroom)} headroom afterwards
            </dd>
          </div>
        </dl>
        {scenario.protected_monthly_buffer && (
          <p className="text-sm text-muted-foreground">
            Protected monthly buffer used: {formatGbp(scenario.protected_monthly_buffer)}.
          </p>
        )}
        {scenario.selected_existing_commitment_description && (
          <p className="text-sm text-muted-foreground">
            Replaces {scenario.selected_existing_commitment_description}
            {scenario.replaced_repayment
              ? ` at ${formatGbp(scenario.replaced_repayment)} per month`
              : ''}
          </p>
        )}
        <p className="text-sm text-muted-foreground">
          Saved on {new Date(scenario.created_at).toLocaleDateString('en-GB')}. This is a saved
          comparison, not a recommendation, plan, agreement, or account change.
        </p>
        <p className="text-xs text-muted-foreground">
          Calculation policy: {scenario.calculation_policy_version}. Basis reference:{' '}
          {scenario.basis_snapshot_id}.
        </p>
      </CardContent>
    </Card>
  )
}

export function RepaymentExplorer() {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<string>('additional')
  const [proposed, setProposed] = useState('')
  const [selectedCommitmentId, setSelectedCommitmentId] = useState('')
  const [buffer, setBuffer] = useState('')
  const [errors, setErrors] = useState<FieldError[]>([])
  const [result, setResult] = useState<ScenarioResponse | null>(null)
  const [saveKey, setSaveKey] = useState<string | null>(null)
  const [justSaved, setJustSaved] = useState<SavedScenarioResponse | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  // Switching mode recalculates from the basis snapshot rather than from
  // whatever was on screen, so a value entered for one mode cannot leak
  // into the other.
  function changeMode(next: string) {
    setMode(next)
    setProposed('')
    setSelectedCommitmentId('')
    setErrors([])
    setResult(null)
    setSaveKey(null)
    setStatus(null)
  }

  const basisQuery = useQuery({
    queryKey: ['repayment-scenario-basis'],
    queryFn: async () => {
      const response = await retrieveScenarioBasisRepaymentScenarioBasisGet()
      if (response.error || !response.data) throw new Error('scenario_basis_unavailable')
      return response.data
    },
  })

  const mutation = useMutation({
    mutationFn: async () => {
      const selectedCommitment = basisQuery.data?.existing_repayment_commitments.find(
        (commitment) => commitment.id === selectedCommitmentId,
      )
      const response = await previewRepaymentScenarioRepaymentScenarioPreviewPost({
        body: {
          mode,
          proposed_repayment: proposed,
          replaced_repayment:
            mode === 'change_existing' ? selectedCommitment?.normalized_monthly_amount : null,
          protected_monthly_buffer: buffer.trim() === '' ? null : buffer,
        } as never,
      })
      if (response.error || !response.data) {
        const detail = (response.error as { detail?: { errors?: FieldError[] } })?.detail
        setErrors(detail?.errors ?? [])
        throw new Error('scenario_rejected')
      }
      return response.data as ScenarioResponse
    },
    onMutate: () => {
      setErrors([])
      setStatus(null)
    },
    onSuccess: (data) => {
      setResult(data)
      setSaveKey(crypto.randomUUID())
      setStatus('Comparison updated. Nothing has been changed or agreed.')
    },
  })

  const savedQuery = useQuery({
    queryKey: ['repayment-scenarios'],
    queryFn: async () => {
      const response = await listSavedScenariosRepaymentScenariosGet()
      if (response.error || !response.data) throw new Error('saved_scenarios_unavailable')
      return response.data
    },
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!result || !saveKey) throw new Error('scenario_not_ready')
      const response = await saveScenarioRepaymentScenariosPost({
        body: {
          basis_snapshot_id: result.basis_snapshot_id,
          mode: result.mode,
          selected_existing_commitment_id:
            result.mode === 'change_existing' ? selectedCommitmentId : null,
          proposed_repayment: result.proposed_repayment,
          protected_monthly_buffer: result.protected_monthly_buffer,
        },
        headers: { 'Idempotency-Key': saveKey },
      })
      if (response.error || !response.data) throw new Error('scenario_save_rejected')
      return response.data
    },
    onMutate: () => setStatus(null),
    onSuccess: (saved) => {
      setJustSaved(saved)
      setStatus('Scenario saved. Your statement and any agreement remain unchanged.')
      void queryClient.invalidateQueries({ queryKey: ['repayment-scenarios'] })
    },
    onError: () => {
      setStatus('The scenario was not saved. Your statement and comparison are unchanged.')
    },
  })

  const savedScenarios = savedQuery.data?.scenarios ?? []
  const visibleSaved = justSaved && !savedScenarios.some((item) => item.id === justSaved.id)
    ? [justSaved, ...savedScenarios]
    : savedScenarios

  if (basisQuery.isError || savedQuery.isError) {
    return (
      <LoadError
        subject="repayment comparison"
        className="mx-auto w-full max-w-3xl"
        retrying={basisQuery.isFetching || savedQuery.isFetching}
        onRetry={() => {
          void basisQuery.refetch()
          void savedQuery.refetch()
        }}
      />
    )
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      {status && (
        <p role="status" className="text-sm text-muted-foreground">
          {status}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Explore a repayment</CardTitle>
          <CardDescription>
            See what a repayment would leave you each month. Nothing here is a recommendation, and
            nothing is saved or agreed.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm text-muted-foreground" htmlFor="scenario-mode">
              What to compare
            </label>
            <select
              id="scenario-mode"
              aria-label="What to compare"
              className="border-input bg-background h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs"
              value={mode}
              onChange={(event) => changeMode(event.target.value)}
            >
              {MODES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {mode === 'change_existing' && (
              <div>
                <label className="text-sm text-muted-foreground" htmlFor="scenario-commitment">
                  Repayment to change
                </label>
                <select
                  id="scenario-commitment"
                  aria-label="Repayment to change"
                  className="border-input bg-background h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs"
                  value={selectedCommitmentId}
                  onChange={(event) => {
                    setSelectedCommitmentId(event.target.value)
                    setResult(null)
                    setSaveKey(null)
                  }}
                >
                  <option value="">Choose a repayment commitment</option>
                  {(basisQuery.data?.existing_repayment_commitments ?? []).map((commitment) => (
                    <option key={commitment.id} value={commitment.id}>
                      {commitment.description} ({formatGbp(commitment.normalized_monthly_amount)} per
                      month)
                    </option>
                  ))}
                </select>
                {basisQuery.data?.existing_repayment_commitments.length === 0 && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    Your basis statement has no existing repayment commitments to change.
                  </p>
                )}
              </div>
            )}
            <AmountField
              id="scenario-proposed"
              label="Amount you are considering"
              field="proposed_repayment"
              value={proposed}
              onChange={setProposed}
              errors={errors}
            />
            <AmountField
              id="scenario-buffer"
              label="Monthly buffer you want to keep (optional)"
              field="protected_monthly_buffer"
              value={buffer}
              onChange={setBuffer}
              errors={errors}
            />
          </div>

          <Button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
            Compare this repayment
          </Button>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-3">
          <ScenarioResultPanel result={result} />
          <Button
            type="button"
            disabled={
              saveMutation.isPending ||
              (result.mode === 'change_existing' && selectedCommitmentId === '')
            }
            onClick={() => saveMutation.mutate()}
          >
            Save scenario
          </Button>
        </div>
      )}

      {visibleSaved.length > 0 && (
        <section className="space-y-4" aria-labelledby="saved-scenarios-title">
          <h2 id="saved-scenarios-title" className="text-xl font-semibold">
            Saved scenarios
          </h2>
          <p className="text-sm text-muted-foreground">
            Saved separately from your financial-statement history.
          </p>
          {visibleSaved.map((scenario) => (
            <SavedScenarioCard key={scenario.id} scenario={scenario} />
          ))}
        </section>
      )}
    </div>
  )
}
