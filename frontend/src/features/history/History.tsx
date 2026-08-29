import { Fragment, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { Info, Minus, TrendingDown, TrendingUp } from 'lucide-react'

import {
  correctConfirmedSnapshotHistorySnapshotIdCorrectPost,
  getHistoryHistoryGet,
  retrieveFinancialStatementFinancialStatementGet,
} from '@/api/generated'
import type {
  ChangeExplanationOut,
  EditableStatementResponse,
  HistoryResponse,
  StatementEntryOut,
} from '@/api/generated'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { LoadError } from '@/components/LoadError'
import { compareMoney, formatGbp, formatPeriod, magnitudeOfMoney } from '@/lib/format'
import { warningCopy } from '@/lib/warning-copy'

const PAGE_SIZE = 12

function correctionEntry(entry: StatementEntryOut) {
  const classification = entry.classification
  return {
    entry_id: entry.entry_id,
    description: entry.description,
    amount: entry.original_amount,
    frequency: entry.original_frequency,
    ...(classification?.display_category && classification.outgoing_treatment
      ? {
          classification: {
            display_category: classification.display_category,
            outgoing_treatment: classification.outgoing_treatment,
            remember: false,
          },
        }
      : {}),
  }
}

function correctionBody(editable: EditableStatementResponse, correctionReason: string) {
  const statement = editable.statement
  return {
    statement_period: statement.statement_period,
    currency: statement.currency,
    income_entries: statement.income_entries.map(correctionEntry),
    outgoing_entries: statement.outgoing_entries.map(correctionEntry),
    repayment_commitments: statement.repayment_commitments.map(correctionEntry),
    resilience: statement.resilience,
    looking_ahead: {
      irregular_costs: statement.looking_ahead.irregular_costs.map(correctionEntry),
      protected_future_provisions:
        statement.looking_ahead.protected_future_provisions.map(correctionEntry),
      expected_changes: statement.looking_ahead.expected_changes.map((change) => ({
        entry_id: change.entry_id,
        description: change.description,
        kind: change.kind,
        amount: change.original_amount,
        frequency: change.original_frequency,
      })),
    },
    correction_reason: correctionReason,
  }
}

function identifierLabel(value: string): string {
  return value.replaceAll('_', ' ')
}

function StoredEntries({
  title,
  entries,
}: {
  title: string
  entries: HistoryResponse['snapshots'][number]['income_entries']
}) {
  return (
    <section>
      <h3 className="font-medium">{title}</h3>
      {entries.length === 0 ? (
        <p className="mt-1 text-muted-foreground">Nothing reported.</p>
      ) : (
        <ul className="mt-1 space-y-2">
          {entries.map((entry) => (
            <li key={entry.entry_id}>
              <span className="font-medium">{entry.description}</span>
              <span className="block text-muted-foreground">
                {formatGbp(entry.original_amount)} {entry.original_frequency}
                {entry.original_frequency !== 'monthly' && (
                  <> · {formatGbp(entry.normalized_monthly_amount)} per month</>
                )}
              </span>
              {entry.classification?.display_category && (
                <span className="block capitalize text-muted-foreground">
                  {identifierLabel(entry.classification.display_category)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function ChangeSummary({ change }: { change: ChangeExplanationOut }) {
  if (change.is_baseline) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Your starting point</CardTitle>
          <CardDescription>{formatPeriod(change.current_period)}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            This is the first statement you have confirmed, so there is nothing to compare it
            with yet. Once you confirm another one, this will show exactly what moved.
          </p>
        </CardContent>
      </Card>
    )
  }

  const total = change.monthly_headroom_change ?? '0'
  const comparison = compareMoney(total, '0')
  const Icon = comparison > 0 ? TrendingUp : comparison < 0 ? TrendingDown : Minus
  const direction = comparison > 0 ? 'more' : comparison < 0 ? 'less' : 'the same'
  const magnitude = formatGbp(magnitudeOfMoney(total))

  return (
    <Card>
      <CardHeader>
        <CardDescription>
          {formatPeriod(change.previous_period as string)} to {formatPeriod(change.current_period)}
        </CardDescription>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Icon aria-hidden="true" className="size-5" />
          {comparison === 0 ? (
            <span>Your monthly headroom is the same</span>
          ) : (
            <span>
              You have {magnitude} {direction} each month
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {change.increases.length > 0 && (
          <div>
            <h3 className="text-sm font-medium">What helped</h3>
            <ul className="mt-1 space-y-1">
              {change.increases.map((item) => (
                <li key={`${item.section}-${item.description}`} className="text-sm text-muted-foreground">
                  {item.description}: {formatGbp(item.previous_monthly)} to{' '}
                  {formatGbp(item.current_monthly)} a month, worth{' '}
                  <span className="text-foreground">
                    {formatGbp(item.signed_headroom_effect)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {change.decreases.length > 0 && (
          <div>
            <h3 className="text-sm font-medium">What reduced it</h3>
            <ul className="mt-1 space-y-1">
              {change.decreases.map((item) => (
                <li key={`${item.section}-${item.description}`} className="text-sm text-muted-foreground">
                  {item.description}: {formatGbp(item.previous_monthly)} to{' '}
                  {formatGbp(item.current_monthly)} a month, worth{' '}
                  <span className="text-foreground">
                    {formatGbp(item.signed_headroom_effect)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-sm text-muted-foreground">
          These are the amounts you reported. This does not say why anything changed.
        </p>

        {change.warnings.length > 0 && (
          <Alert>
            <Info />
            <AlertTitle>Limitations</AlertTitle>
            <AlertDescription>
              <ul>
                {change.warnings.map((warning) => (
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

function SeriesTable({ series }: { series: HistoryResponse['series'] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Monthly headroom over time</CardTitle>
        <CardDescription>
          One row for each statement period you have confirmed, with the exact amounts.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm" aria-label="Monthly headroom over time">
          <thead>
            <tr className="border-b text-left">
              <th scope="col" className="py-2 pr-4 font-medium">Period</th>
              <th scope="col" className="py-2 pr-4 font-medium">Income</th>
              <th scope="col" className="py-2 pr-4 font-medium">Outgoings</th>
              <th scope="col" className="py-2 pr-4 font-medium">Monthly headroom</th>
            </tr>
          </thead>
          <tbody>
            {series.map((point) => (
              <tr key={point.statement_period} className="border-b last:border-0">
                <th scope="row" className="py-2 pr-4 text-left font-normal">
                  {formatPeriod(point.statement_period)}
                </th>
                <td className="py-2 pr-4">{formatGbp(point.normalized_monthly_income)}</td>
                <td className="py-2 pr-4">{formatGbp(point.normalized_monthly_outgoings)}</td>
                <td className="py-2 pr-4 font-medium">{formatGbp(point.monthly_headroom)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

function RecordsTable({
  snapshots,
  total,
  offset,
  onOlder,
  onNewer,
}: {
  snapshots: HistoryResponse['snapshots']
  total: number
  offset: number
  onOlder: () => void
  onNewer: () => void
}) {
  const [expandedSnapshotId, setExpandedSnapshotId] = useState<string | null>(null)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Every confirmed record</CardTitle>
        <CardDescription>
          Corrections add a new record and never replace an earlier one, so a period can appear
          more than once.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 overflow-x-auto">
        <table className="w-full text-sm" aria-label="Every confirmed record">
          <thead>
            <tr className="border-b text-left">
              <th scope="col" className="py-2 pr-4 font-medium">Period</th>
              <th scope="col" className="py-2 pr-4 font-medium">Confirmed</th>
              <th scope="col" className="py-2 pr-4 font-medium">Monthly headroom</th>
              <th scope="col" className="py-2 pr-4 font-medium">Status</th>
              <th scope="col" className="py-2 pr-4 font-medium">Calculated with</th>
              <th scope="col" className="py-2 font-medium">Statement</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map((snapshot) => {
              const period = formatPeriod(snapshot.statement_period)
              const expanded = expandedSnapshotId === snapshot.snapshot_id
              return (
                <Fragment key={snapshot.snapshot_id}>
                  <tr className="border-b last:border-0">
                    <th scope="row" className="py-2 pr-4 text-left font-normal">
                      {period}
                    </th>
                    <td className="py-2 pr-4">
                      {new Date(snapshot.confirmed_at).toLocaleDateString('en-GB')}
                    </td>
                    <td className="py-2 pr-4 font-medium">
                      {formatGbp(snapshot.monthly_headroom)}
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground">
                      {snapshot.is_effective ? (
                        <span>In effect</span>
                      ) : (
                        <span>Superseded by a later correction</span>
                      )}
                      {snapshot.correction_reason && (
                        <span className="block">Reason given: {snapshot.correction_reason}</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground">
                      {snapshot.calculation_policy_version}
                    </td>
                    <td className="py-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        aria-expanded={expanded}
                        aria-label={`${expanded ? 'Hide' : 'View'} ${period} statement details`}
                        onClick={() =>
                          setExpandedSnapshotId(expanded ? null : snapshot.snapshot_id)
                        }
                      >
                        {expanded ? 'Hide details' : 'View details'}
                      </Button>
                    </td>
                  </tr>
                  {expanded && (
                    <tr className="border-b bg-muted/30">
                      <td colSpan={6} className="p-4">
                        <div className="grid gap-4 sm:grid-cols-2">
                          <StoredEntries title="Income" entries={snapshot.income_entries} />
                          <StoredEntries title="Outgoings" entries={snapshot.outgoing_entries} />
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>

        {total > snapshots.length && (
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={onNewer} disabled={offset === 0}>
              Newer
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={onOlder}
              disabled={offset + snapshots.length >= total}
            >
              Older
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function History() {
  const [offset, setOffset] = useState(0)
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['history', offset],
    queryFn: async () => {
      const result = await getHistoryHistoryGet({
        query: { limit: PAGE_SIZE, offset },
      })
      if (result.error || !result.data) throw new Error('history_unavailable')
      return result.data as HistoryResponse
    },
    placeholderData: keepPreviousData,
  })

  if (query.isLoading) {
    return (
      <Card className="mx-auto w-full max-w-3xl">
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-24 w-full" />
        </CardContent>
        <p role="status" className="sr-only">
          Loading your confirmed history&hellip;
        </p>
      </Card>
    )
  }

  if (query.isError || !query.data) {
    return (
      <LoadError
        subject="history"
        className="mx-auto w-full max-w-3xl"
        retrying={query.isFetching}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const { snapshots, series, latest_change: change, total } = query.data

  if (total === 0) {
    return (
      <Card className="mx-auto w-full max-w-3xl">
        <CardHeader>
          <CardTitle className="text-lg">Nothing confirmed yet</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Once you review and confirm a statement, it is saved here and you can see how your
            position changes over time.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      {change && <ChangeSummary change={change} />}
      <SeriesTable series={series} />

      {series.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Something not right?</CardTitle>
            <CardDescription>
              You can correct the record currently in effect. Nothing is ever overwritten.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CorrectionPanel
              snapshotId={series[series.length - 1].snapshot_id}
              period={series[series.length - 1].statement_period}
              onDone={() => queryClient.invalidateQueries({ queryKey: ['history'] })}
            />
          </CardContent>
        </Card>
      )}
      <RecordsTable
        snapshots={snapshots}
        total={total}
        offset={offset}
        onOlder={() => setOffset(offset + PAGE_SIZE)}
        onNewer={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
      />
    </div>
  )
}

function CorrectionPanel({
  snapshotId,
  period,
  onDone,
}: {
  snapshotId: string
  period: string
  onDone: () => void
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [conflict, setConflict] = useState<string | null>(null)
  const correctionKey = useRef<{ reason: string; key: string } | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      const editable = await retrieveFinancialStatementFinancialStatementGet({
        query: { statement_period: period },
      })
      if (editable.error || !editable.data) {
        throw new Error('correction_statement_unavailable')
      }
      if (correctionKey.current?.reason !== reason) {
        correctionKey.current = { reason, key: crypto.randomUUID() }
      }
      const result = await correctConfirmedSnapshotHistorySnapshotIdCorrectPost({
        path: { snapshot_id: snapshotId },
        body: correctionBody(editable.data, reason) as never,
        headers: { 'Idempotency-Key': correctionKey.current.key },
      })
      if (result.error || !result.data) {
        const detail = (result.error as { detail?: { message?: string } })?.detail
        setConflict(detail?.message ?? 'We could not save that correction. Please try again.')
        throw new Error('correction_rejected')
      }
      return result.data
    },
    onMutate: () => setConflict(null),
    onSuccess: () => {
      correctionKey.current = null
      setOpen(false)
      setReason('')
      onDone()
    },
  })

  if (!open) {
    return (
      <Button
        type="button"
        variant="outline"
        aria-label={`Correct the ${formatPeriod(period)} record`}
        onClick={() => setOpen(true)}
      >
        Correct this record
      </Button>
    )
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div>
        <h3 className="font-medium">Correct the {formatPeriod(period)} record</h3>
        <p className="text-sm text-muted-foreground">
          Correcting adds a new record for this period. The original stays in your history so the
          change is always visible.
        </p>
        <p className="text-sm text-muted-foreground">
          This uses the values in your currently saved statement. If an amount is wrong,{' '}
          <a className="underline" href="/statement">
            update your information first
          </a>
          .
        </p>
      </div>

      <div>
        <label className="text-sm text-muted-foreground" htmlFor="correction-reason">
          What was wrong?
        </label>
        <Input
          id="correction-reason"
          type="text"
          aria-label="What was wrong"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>

      {conflict && (
        <Alert>
          <Info />
          <AlertTitle>This record changed</AlertTitle>
          <AlertDescription>{conflict}</AlertDescription>
        </Alert>
      )}

      <div className="flex gap-2">
        <Button
          type="button"
          disabled={!reason.trim() || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          Save this correction
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
