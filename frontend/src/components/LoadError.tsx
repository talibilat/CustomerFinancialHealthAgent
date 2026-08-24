import { AlertTriangle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

type LoadErrorProps = {
  subject: string
  onRetry: () => void
  retrying?: boolean
  className?: string
}

export function LoadError({ subject, onRetry, retrying = false, className }: LoadErrorProps) {
  return (
    <Alert variant="destructive" className={className}>
      <AlertTriangle aria-hidden="true" />
      <AlertTitle>We can&apos;t reach the server right now</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>Your {subject} hasn&apos;t been lost - please try again in a moment.</p>
        <Button type="button" variant="outline" disabled={retrying} onClick={onRetry}>
          {retrying ? 'Trying again…' : 'Try again'}
        </Button>
      </AlertDescription>
    </Alert>
  )
}
