import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FlaskConical, RotateCcw } from 'lucide-react'
import { useState } from 'react'

import {
  listDemoPresetsDemoPresetsGet,
  resetDemoDemoResetPost,
} from '@/api/generated'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'

export function DemoPresetPicker() {
  const queryClient = useQueryClient()
  const [pendingCode, setPendingCode] = useState('')
  const [announcement, setAnnouncement] = useState('')
  const presets = useQuery({
    queryKey: ['demo-presets'],
    queryFn: async () => {
      const result = await listDemoPresetsDemoPresetsGet()
      if (result.error || !result.data) throw new Error('demo_presets_unavailable')
      return result.data.presets
    },
  })
  const reset = useMutation({
    mutationFn: async (preset: string) => {
      const result = await resetDemoDemoResetPost({
        body: { preset, confirmed_reset: true },
      })
      if (result.error || !result.data) throw new Error('demo_reset_failed')
      return result.data
    },
    onSuccess: async (result) => {
      setPendingCode('')
      setAnnouncement(result.message)
      await queryClient.invalidateQueries()
    },
    onError: () => setAnnouncement('The demo preset could not be loaded. Your current view is unchanged.'),
  })
  const selected = presets.data?.find((preset) => preset.code === pendingCode)

  if (presets.isError) return null

  return (
    <Card className="mx-auto w-full max-w-xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <FlaskConical aria-hidden="true" />
          Try a fictional situation
        </CardTitle>
        <CardDescription>
          These controlled presets make difficult and edge-case journeys quick to review.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="demo-preset">Demonstration preset</Label>
          <select
            id="demo-preset"
            className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm"
            value={pendingCode}
            onChange={(event) => {
              setPendingCode(event.target.value)
              setAnnouncement('')
            }}
            disabled={presets.isLoading || reset.isPending}
          >
            <option value="">Choose a fictional preset</option>
            {presets.data?.map((preset) => (
              <option key={preset.code} value={preset.code}>{preset.label}</option>
            ))}
          </select>
        </div>

        {selected && (
          <Alert role="alert">
            <RotateCcw aria-hidden="true" />
            <AlertTitle>Fictional demo data will be reset</AlertTitle>
            <AlertDescription className="space-y-3">
              <p>{selected.description}</p>
              <p>This replaces the active fictional demo view. It does not change another customer&apos;s records.</p>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={() => reset.mutate(selected.code)} disabled={reset.isPending}>
                  {reset.isPending ? 'Loading preset…' : `Load ${selected.label}`}
                </Button>
                <Button type="button" variant="outline" onClick={() => setPendingCode('')} disabled={reset.isPending}>
                  Cancel
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

        <p role="status" aria-live="polite" className={announcement ? 'text-sm' : 'sr-only'}>
          {announcement}
        </p>
      </CardContent>
    </Card>
  )
}
