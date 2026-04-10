import { useEffect, useState } from 'react'
import { Activity, AlertTriangle } from 'lucide-react'

import {
  listSimulations,
  type SimulationStatus,
} from '@/api/endpoints/clients'
import { EmptyState } from '@/components/ui/empty-state'
import { MetricCard } from '@/components/ui/metric-card'
import { SectionCard } from '@/components/ui/section-card'
import { SkeletonCard } from '@/components/ui/skeleton'
import { createLogger } from '@/lib/logger'

const log = createLogger('SimulationDashboardPage')

/**
 * Simulation run overview.
 *
 * Aggregates metrics across every known simulation record so
 * operators get a single-glance view of throughput and
 * acceptance rates. Detailed charts and live-stream updates land
 * in the next iteration.
 */
export default function SimulationDashboardPage() {
  const [runs, setRuns] = useState<readonly SimulationStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const result = await listSimulations({ limit: 100 })
        setRuns(result.data)
        setError(null)
      } catch (err) {
        log.error('list_simulations_failed', err)
        setError('Failed to load simulation runs.')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  if (loading && runs.length === 0) {
    return (
      <div className="space-y-section-gap">
        <h1 className="text-lg font-semibold text-foreground">Simulations</h1>
        <SkeletonCard />
      </div>
    )
  }

  const totalTasksCreated = runs.reduce(
    (sum, run) => sum + run.metrics.total_tasks_created,
    0,
  )
  const totalAccepted = runs.reduce(
    (sum, run) => sum + run.metrics.tasks_accepted,
    0,
  )
  const totalRejected = runs.reduce(
    (sum, run) => sum + run.metrics.tasks_rejected,
    0,
  )
  const runningCount = runs.filter((run) => run.status === 'running').length

  return (
    <div className="space-y-section-gap">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Simulations</h1>
        <span className="text-sm text-muted-foreground">
          {runs.length} runs
        </span>
      </div>

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-grid-gap md:grid-cols-4">
        <MetricCard label="Active runs" value={runningCount.toString()} />
        <MetricCard
          label="Tasks created"
          value={totalTasksCreated.toString()}
        />
        <MetricCard label="Accepted" value={totalAccepted.toString()} />
        <MetricCard label="Rejected" value={totalRejected.toString()} />
      </div>

      {runs.length === 0 ? (
        <EmptyState
          icon={Activity}
          title="No simulation runs yet"
          description="Start a simulation via POST /simulations to populate this dashboard."
        />
      ) : (
        <SectionCard title="Recent runs" icon={Activity}>
          <ul className="space-y-2">
            {runs.map((run) => (
              <li
                key={run.simulation_id}
                className="flex items-center justify-between rounded-md border border-border bg-card-hover p-card text-sm"
              >
                <div>
                  <div className="font-medium text-foreground">
                    {run.simulation_id}
                  </div>
                  <div className="text-xs text-text-secondary">
                    {run.config.project_id} ·{' '}
                    {run.config.rounds} round(s)
                  </div>
                </div>
                <span
                  className="rounded-full border border-border px-2 py-1 text-xs text-foreground"
                  aria-label={`Status: ${run.status}`}
                >
                  {run.status}
                </span>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
    </div>
  )
}
