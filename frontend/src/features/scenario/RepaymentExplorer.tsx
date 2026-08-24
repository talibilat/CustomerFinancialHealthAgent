import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Info } from 'lucide-react'

import { previewRepaymentScenarioRepaymentScenarioPreviewPost } from '@/api/generated'
import type { ScenarioResponse } from '@/api/generated'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
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

export function RepaymentExplorer() {
  const [mode, setMode] = useState<string>('additional')
  const [proposed, setProposed] = useState('')
  const [replaced, setReplaced] = useState('')
  const [buffer, setBuffer] = useState('')
  const [errors, setErrors] = useState<FieldError[]>([])
  const [result, setResult] = useState<ScenarioResponse | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  // Switching mode recalculates from the basis snapshot rather than from
  // whatever was on screen, so a value entered for one mode cannot leak
  // into the other.
  function changeMode(next: string) {
    setMode(next)
    setProposed('')
    setReplaced('')
    setErrors([])
    setResult(null)
    setStatus(null)
  }

  const mutation = useMutation({
    mutationFn: async () => {
      const response = await previewRepaymentScenarioRepaymentScenarioPreviewPost({
        body: {
          mode,
          proposed_repayment: proposed,
          replaced_repayment: mode === 'change_existing' ? replaced : null,
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
      setStatus('Comparison updated. Nothing has been changed or agreed.')
    },
  })

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
              <AmountField
                id="scenario-replaced"
                label="Amount you pay now"
                field="replaced_repayment"
                value={replaced}
                onChange={setReplaced}
                errors={errors}
              />
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

      {result && <ScenarioResultPanel result={result} />}
    </div>
  )
}
