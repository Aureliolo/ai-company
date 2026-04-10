import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import {
  AlertTriangle,
  CheckCircle,
  MinusCircle,
  ShieldCheck,
  XCircle,
} from 'lucide-react'

import {
  getReviewPipeline,
  type PipelineResult,
  type ReviewStageResult,
} from '@/api/endpoints/clients'
import { SectionCard } from '@/components/ui/section-card'
import { SkeletonCard } from '@/components/ui/skeleton'
import { createLogger } from '@/lib/logger'

const log = createLogger('ReviewPipelinePage')

function VerdictIcon({
  verdict,
}: {
  verdict: ReviewStageResult['verdict']
}) {
  if (verdict === 'pass') {
    return <CheckCircle className="size-4 text-success" aria-label="Pass" />
  }
  if (verdict === 'fail') {
    return <XCircle className="size-4 text-danger" aria-label="Fail" />
  }
  return <MinusCircle className="size-4 text-warning" aria-label="Skip" />
}

/**
 * Review pipeline visualization for a single task.
 *
 * Resolves the task via the review controller and renders the
 * per-stage breakdown with verdict icons, reasons, and timing.
 */
export default function ReviewPipelinePage() {
  const { taskId } = useParams<{ taskId: string }>()
  const [pipeline, setPipeline] = useState<PipelineResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!taskId) {
      const timer = setTimeout(() => {
        setError('Missing task id in URL')
        setLoading(false)
      }, 0)
      return () => clearTimeout(timer)
    }
    const load = async () => {
      try {
        const result = await getReviewPipeline(taskId)
        setPipeline(result)
        setError(null)
      } catch (err) {
        log.error('get_review_pipeline_failed', err)
        setError('Failed to load review pipeline for this task.')
      } finally {
        setLoading(false)
      }
    }
    void load()
    return undefined
  }, [taskId])

  if (loading) {
    return (
      <div className="space-y-section-gap">
        <h1 className="text-lg font-semibold text-foreground">
          Review Pipeline
        </h1>
        <SkeletonCard />
      </div>
    )
  }

  if (error || !pipeline) {
    return (
      <div className="space-y-section-gap">
        <h1 className="text-lg font-semibold text-foreground">
          Review Pipeline
        </h1>
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error ?? 'Pipeline result not available.'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      <div>
        <h1 className="text-lg font-semibold text-foreground">
          Review Pipeline
        </h1>
        <p className="text-sm text-text-secondary">Task {pipeline.task_id}</p>
      </div>

      <SectionCard title="Overall verdict" icon={ShieldCheck}>
        <div className="flex items-center gap-2 text-sm">
          <VerdictIcon verdict={pipeline.final_verdict} />
          <span className="font-medium text-foreground">
            {pipeline.final_verdict.toUpperCase()}
          </span>
          <span className="text-text-secondary">
            · {pipeline.total_duration_ms} ms
          </span>
        </div>
      </SectionCard>

      <SectionCard title="Stage breakdown" icon={ShieldCheck}>
        <ul className="space-y-3">
          {pipeline.stage_results.map((stage) => (
            <li
              key={stage.stage_name}
              className="rounded-md border border-border bg-card-hover p-card text-sm"
            >
              <div className="flex items-center gap-2">
                <VerdictIcon verdict={stage.verdict} />
                <span className="font-medium text-foreground">
                  {stage.stage_name}
                </span>
                <span className="ml-auto text-xs text-text-secondary">
                  {stage.duration_ms} ms
                </span>
              </div>
              {stage.reason && (
                <p className="mt-2 text-text-secondary">{stage.reason}</p>
              )}
            </li>
          ))}
        </ul>
      </SectionCard>
    </div>
  )
}
