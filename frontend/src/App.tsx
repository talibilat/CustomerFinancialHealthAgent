import { Overview } from '@/features/overview/Overview'

function App() {
  return (
    <div className="min-h-svh bg-muted/30">
      <main className="mx-auto max-w-3xl px-4 py-10 sm:py-16">
        <h1 className="mb-8 text-center text-2xl font-semibold tracking-tight text-foreground">
          Your financial-health overview
        </h1>
        <Overview />
      </main>
    </div>
  )
}

export default App
