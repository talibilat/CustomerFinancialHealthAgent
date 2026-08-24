import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Info, Minus, TrendingDown, TrendingUp } from 'lucide-react'

import {
  getOverviewOverviewGet,
  requestPersonalizedExplanationOverviewPersonalizedExplanationPost,
} from '@/api/generated'
import type {
  DifficultyOut,
  MoneyEntryOut,
  OverviewResponse,
  PersonalizedExplanationOut,
  ResilienceOut,
} from '@/api/generated'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { LoadError } from '@/components/LoadError'
import { formatFrequency, formatGbp, formatPeriod } from '@/lib/format'
import { DemoPresetPicker } from './DemoPresetPicker'

const RESULT_PRESENTATION: Record<
  string,
  { label: string; icon: typeof TrendingUp; badgeVariant: 'secondary' | 'destructive' | 'outline' }
> = {
  surplus: { label: 'Income above outgoings', icon: TrendingUp, badgeVariant: 'secondary' },
  shortfall: { label: 'Outgoings above income', icon: TrendingDown, badgeVariant: 'destructive' },
  balanced: { label: 'Income equal to outgoings', icon: Minus, badgeVariant: 'outline' },
  zero_income: { label: 'No income reported', icon: TrendingDown, badgeVariant: 'destructive' },
  incomplete_information: { label: 'Information incomplete', icon: Info, badgeVariant: 'outline' },
}

function ResultBadge({ resultCode }: { resultCode: string }) {
  const presentation = RESULT_PRESENTATION[resultCode] ?? RESULT_PRESENTATION.balanced
  const Icon = presentation.icon
  return (
    <Badge variant={presentation.badgeVariant}>
      <Icon aria-hidden="true" />
      {presentation.label}
    </Badge>
  )
}

function StatBlock({ label, amount, emphasize = false }: { label: string; amount: string; emphasize?: boolean }) {
  return (
    <div>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className={emphasize ? 'text-3xl font-semibold tracking-tight' : 'text-xl font-medium'}>
        {formatGbp(amount)}
      </p>
    </div>
  )
}

function EntryList({ title, entries }: { title: string; entries: MoneyEntryOut[] }) {
  return (
    <div>
      <h4 className="text-sm font-medium">{title}</h4>
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">No entries reported.</p>
      ) : (
        <ul className="mt-1 space-y-1">
          {entries.map((entry, index) => (
            <li key={index} className="text-sm text-muted-foreground">
              {formatGbp(entry.original_amount)} ({formatFrequency(entry.original_frequency)}) normalizes to{' '}
              <span className="text-foreground">{formatGbp(entry.normalized_monthly_amount)}</span> per month
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const RESILIENCE_PRESENTATION: Record<string, { label: string; badgeVariant: 'secondary' | 'destructive' | 'outline' }> = {
  above_reserve: { label: 'Above protected reserve', badgeVariant: 'secondary' },
  at_reserve: { label: 'At protected reserve', badgeVariant: 'outline' },
  below_reserve: { label: 'Below protected reserve', badgeVariant: 'destructive' },
}

function ResilienceBadge({ resultCode }: { resultCode: string }) {
  const presentation = RESILIENCE_PRESENTATION[resultCode]
  if (!presentation) return null
  return <Badge variant={presentation.badgeVariant}>{presentation.label}</Badge>
}

// Each reported figure stands on its own: the customer may supply a balance or
// arrears without supplying savings and a reserve, and vice versa. Derived
// figures are omitted when zero because they only add noise at that value.
function reportedResilienceFigures(resilience: ResilienceOut): { label: string; amount: string }[] {
  const candidates: { label: string; amount: string | null; hideWhenZero?: boolean }[] = [
    { label: 'Accessible savings', amount: resilience.accessible_savings },
    { label: 'Protected reserve', amount: resilience.protected_reserve },
    { label: 'Reserve gap', amount: resilience.reserve_gap, hideWhenZero: true },
    { label: 'Savings above reserve', amount: resilience.savings_above_reserve, hideWhenZero: true },
    { label: 'Current-account balance', amount: resilience.current_account_balance },
    { label: 'Known arrears', amount: resilience.known_arrears },
  ]

  return candidates.filter(
    (candidate): candidate is { label: string; amount: string } =>
      candidate.amount !== null && !(candidate.hideWhenZero && Number(candidate.amount) === 0),
  )
}

function ResilienceCard({ resilience }: { resilience: ResilienceOut }) {
  const reportedFigures = reportedResilienceFigures(resilience)

  return (
    <Card className="mx-auto w-full max-w-xl">
      <CardHeader>
        <CardTitle className="text-lg">Financial resilience</CardTitle>
        {resilience.result_code && (
          <CardAction>
            <ResilienceBadge resultCode={resilience.result_code} />
          </CardAction>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {reportedFigures.length > 0 && (
          <div className="grid grid-cols-2 gap-4">
            {reportedFigures.map((figure) => (
              <StatBlock key={figure.label} label={figure.label} amount={figure.amount} />
            ))}
          </div>
        )}

        {resilience.result_code === null && (
          <p className="text-sm text-muted-foreground">
            Add accessible savings and a protected reserve to see how your savings compare. This does not affect
            your monthly position above.
          </p>
        )}

        <p className="text-sm text-muted-foreground">
          Accessible savings are a separate resilience picture and never become monthly income or offset a
          shortfall.
        </p>

        {resilience.warnings.length > 0 && (
          <Alert>
            <Info />
            <AlertTitle>Limitations</AlertTitle>
            <AlertDescription>
              <ul>
                {resilience.warnings.map((warning) => (
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

function DifficultyCard({ difficulty }: { difficulty: DifficultyOut }) {
  if (difficulty.result_code === 'no_difficulty_identified') return null

  return (
    <Alert className="mx-auto w-full max-w-xl" role="status" aria-live="polite">
      <Info aria-hidden="true" />
      <AlertTitle>{difficulty.title}</AlertTitle>
      <AlertDescription className="space-y-4">
        <p>{difficulty.explanation}</p>
        {difficulty.result_code === 'protected_outgoings_not_covered' && (
          <p>Protected monthly outgoings: {formatGbp(difficulty.protected_monthly_outgoings)}</p>
        )}
        {difficulty.support_routes.length > 0 && (
          <div>
            <p className="font-medium text-foreground">Support and next steps</p>
            <ul className="mt-2 space-y-3">
              {difficulty.support_routes.map((route) => (
                <li key={route.code}>
                  <a
                    className="font-medium underline underline-offset-4"
                    href={route.url}
                    {...(route.external ? { target: '_blank', rel: 'noreferrer' } : {})}
                  >
                    {route.label}
                    {route.external ? ' (opens in a new tab)' : ''}
                  </a>
                  <p>{route.description}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </AlertDescription>
    </Alert>
  )
}

function ExplanationCard({ overview }: { overview: OverviewResponse }) {
  const [personalized, setPersonalized] = useState<PersonalizedExplanationOut | null>(
    overview.personalized_explanation ?? null,
  )
  const mutation = useMutation({
    mutationFn: async () => {
      const result = await requestPersonalizedExplanationOverviewPersonalizedExplanationPost({
        body: { snapshot_id: overview.snapshot_id },
        headers: {
          'Idempotency-Key': `guidance-${overview.snapshot_id}-${Date.now()}`,
        },
      })
      if (result.error || !result.data) throw new Error('personalized_explanation_unavailable')
      return result.data
    },
    onSuccess: (result) => {
      if (result.snapshot_id === overview.snapshot_id) setPersonalized(result)
    },
  })

  const personalizationUnavailable =
    mutation.isError || (personalized !== null && personalized.outcome !== 'generated')

  return (
    <Card className="mx-auto w-full max-w-xl">
      <CardHeader>
        <CardTitle className="text-lg">Your explanation</CardTitle>
        <CardDescription>Deterministic information remains the authoritative result.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="font-medium">How the reported figures compare</p>
          <p className="mt-1 text-sm text-muted-foreground">{overview.deterministic_explanation}</p>
        </div>

        {personalized?.outcome === 'generated' && (
          <div>
            <p className="font-medium">Optional personalized wording</p>
            <p className="mt-1 text-sm text-muted-foreground">{personalized.text}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              Created for {formatPeriod(overview.statement_period)}. It does not change the result or support shown.
            </p>
          </div>
        )}

        {personalizationUnavailable && (
          <Alert>
            <Info aria-hidden="true" />
            <AlertTitle>Optional personalization is unavailable</AlertTitle>
            <AlertDescription>
              The deterministic explanation above is complete and your result and support routes are unchanged.
            </AlertDescription>
          </Alert>
        )}

        <Button
          type="button"
          variant="outline"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? 'Creating optional wording...' : 'Explain this more simply'}
        </Button>
        {mutation.isPending && (
          <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
            Creating optional wording. You can continue using the deterministic information and support routes.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function OverviewContent({ overview }: { overview: OverviewResponse }) {
  return (
    <div className="space-y-6">
      <DemoPresetPicker />
      <Card className="mx-auto w-full max-w-xl">
        <CardHeader>
          <CardDescription>{formatPeriod(overview.statement_period)}</CardDescription>
          <CardTitle className="text-lg">Your monthly position</CardTitle>
          <CardAction>
            <ResultBadge resultCode={overview.result_code} />
          </CardAction>
        </CardHeader>

        <CardContent className="space-y-6">
          <div>
            <StatBlock label="Monthly headroom" amount={overview.monthly_headroom} emphasize />
            <div className="mt-4 grid grid-cols-2 gap-4">
              <StatBlock label="Normalized monthly income" amount={overview.normalized_monthly_income} />
              <StatBlock label="Normalized monthly outgoings" amount={overview.normalized_monthly_outgoings} />
            </div>
          </div>

          <p className="text-sm text-muted-foreground">
            This reflects the information reported for this statement period. It is not a proof of long-term
            affordability.
          </p>

          {overview.warnings.length > 0 && (
            <Alert>
              <Info />
              <AlertTitle>Limitations</AlertTitle>
              <AlertDescription>
                <ul>
                  {overview.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          <Separator />

          <Accordion type="single" collapsible>
            <AccordionItem value="calculation" className="border-none">
              <AccordionTrigger>Review how this was calculated</AccordionTrigger>
              <AccordionContent className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Monthly headroom = normalized monthly income &minus; normalized monthly outgoings ={' '}
                  {formatGbp(overview.normalized_monthly_income)} &minus;{' '}
                  {formatGbp(overview.normalized_monthly_outgoings)} = {formatGbp(overview.monthly_headroom)}
                </p>
                <p className="text-sm text-muted-foreground">
                  Calculation policy version: {overview.calculation_policy_version}
                </p>
                <EntryList title="Income" entries={overview.income_entries} />
                <EntryList title="Outgoings" entries={overview.outgoing_entries} />
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </CardContent>
      </Card>

      {overview.difficulty && <DifficultyCard difficulty={overview.difficulty} />}

      <ExplanationCard key={overview.snapshot_id} overview={overview} />

      <ResilienceCard resilience={overview.resilience} />
    </div>
  )
}

function OverviewLoading() {
  return (
    <Card className="mx-auto w-full max-w-xl">
      <CardHeader>
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-5 w-40" />
      </CardHeader>
      <CardContent className="space-y-6">
        <Skeleton className="h-9 w-32" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </CardContent>
      <p role="status" className="sr-only">
        Loading your financial-health overview&hellip;
      </p>
    </Card>
  )
}

export function Overview() {
  const query = useQuery({
    queryKey: ['overview'],
    queryFn: async () => {
      const result = await getOverviewOverviewGet()
      if (result.error || !result.data) {
        throw new Error('overview_unavailable')
      }
      return result.data
    },
  })

  if (query.isLoading) {
    return <OverviewLoading />
  }

  if (query.isError || !query.data) {
    return (
      <LoadError
        subject="information"
        className="mx-auto w-full max-w-xl"
        retrying={query.isFetching}
        onRetry={() => void query.refetch()}
      />
    )
  }

  return <OverviewContent overview={query.data} />
}
