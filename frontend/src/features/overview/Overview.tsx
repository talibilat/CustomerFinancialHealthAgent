import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Info, Minus, TrendingDown, TrendingUp } from 'lucide-react'

import { getOverviewOverviewGet } from '@/api/generated'
import type { MoneyEntryOut, OverviewResponse, ResilienceOut } from '@/api/generated'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'

const gbpFormatter = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
})

const periodFormatter = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' })

function formatGbp(amount: string): string {
  return gbpFormatter.format(Number(amount))
}

function formatFrequency(frequency: string): string {
  return frequency.replace('_', '-')
}

function formatPeriod(statementPeriod: string): string {
  return periodFormatter.format(new Date(`${statementPeriod}T00:00:00Z`))
}

const RESULT_PRESENTATION: Record<
  string,
  { label: string; icon: typeof TrendingUp; badgeVariant: 'secondary' | 'destructive' | 'outline' }
> = {
  surplus: { label: 'Income above outgoings', icon: TrendingUp, badgeVariant: 'secondary' },
  shortfall: { label: 'Outgoings above income', icon: TrendingDown, badgeVariant: 'destructive' },
  balanced: { label: 'Income equal to outgoings', icon: Minus, badgeVariant: 'outline' },
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

function OverviewContent({ overview }: { overview: OverviewResponse }) {
  return (
    <div className="space-y-6">
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
      <Alert variant="destructive" className="mx-auto w-full max-w-xl">
        <AlertTriangle />
        <AlertTitle>We can&apos;t reach the server right now</AlertTitle>
        <AlertDescription>Your information hasn&apos;t been lost - please try again in a moment.</AlertDescription>
      </Alert>
    )
  }

  return <OverviewContent overview={query.data} />
}
