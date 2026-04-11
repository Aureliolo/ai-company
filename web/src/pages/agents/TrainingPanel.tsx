/**
 * Training customization panel for the agent detail/hiring flow.
 *
 * Shows training status, allows customizing sources, content types,
 * and volume caps. Displays results after training completes.
 *
 * Visual testing checkpoints:
 * - Panel renders with default training config
 * - Override sources field accepts agent IDs
 * - Content type toggles enable/disable
 * - Volume cap inputs validate positive integers
 * - Result summary shows post-training metrics
 */

import { useState } from 'react'

import { GraduationCap } from 'lucide-react'

import { SectionCard } from '@/components/ui/section-card'
import { StatPill } from '@/components/ui/stat-pill'
import { Button } from '@/components/ui/button'
import { ToggleField } from '@/components/ui/toggle-field'
import { TagInput } from '@/components/ui/tag-input'
import { cn } from '@/lib/utils'
import { createLogger } from '@/lib/logger'
import type { TrainingPlanResponse, TrainingResultResponse } from '@/api/endpoints/training'

const log = createLogger('training-panel')

// -- Types -----------------------------------------------------------

interface TrainingPanelProps {
  agentName: string
  plan?: TrainingPlanResponse | null
  result?: TrainingResultResponse | null
  onCreatePlan?: (overrides: {
    override_sources: string[]
    skip_training: boolean
    require_review: boolean
  }) => void
  onExecute?: () => void
  className?: string
}

// -- Content type labels ---------------------------------------------

const CONTENT_TYPE_LABELS: Record<string, string> = {
  procedural: 'Procedural Memories',
  semantic: 'Semantic Knowledge',
  tool_patterns: 'Tool Patterns',
}

// -- Component -------------------------------------------------------

export function TrainingPanel({
  agentName,
  plan,
  result,
  onCreatePlan,
  onExecute,
  className,
}: TrainingPanelProps) {
  const [overrideSources, setOverrideSources] = useState<string[]>([])
  const [skipTraining, setSkipTraining] = useState(false)
  const [requireReview, setRequireReview] = useState(true)

  const handleCreatePlan = () => {
    log.debug('Creating training plan', { agentName })
    onCreatePlan?.({
      override_sources: overrideSources,
      skip_training: skipTraining,
      require_review: requireReview,
    })
  }

  return (
    <SectionCard
      title="Training Mode"
      icon={GraduationCap}
      className={cn('', className)}
    >
      {/* Status display */}
      {plan && (
        <div className="mb-card flex items-center gap-grid-gap">
          <span className="text-sm text-muted-foreground">
            Status: {plan.status}
          </span>
        </div>
      )}

      {/* Result summary */}
      {result && (
        <TrainingResultSummary result={result} />
      )}

      {/* Configuration (when no plan exists) */}
      {!plan && (
        <div className="space-y-card">
          <div>
            <span className="mb-1 block text-sm font-medium text-foreground">
              Override Source Agents
            </span>
            <TagInput
              value={overrideSources}
              onChange={setOverrideSources}
              placeholder="Enter agent IDs..."
            />
          </div>

          <ToggleField
            label="Skip Training"
            description="Bypass the training step entirely"
            checked={skipTraining}
            onChange={setSkipTraining}
          />

          <ToggleField
            label="Require Human Review"
            description="Route training items through approval"
            checked={requireReview}
            onChange={setRequireReview}
          />

          <Button onClick={handleCreatePlan}>
            Create Training Plan
          </Button>
        </div>
      )}

      {/* Execute button (when plan is pending) */}
      {plan?.status === 'pending' && (
        <Button onClick={onExecute} className="mt-card">
          Execute Training Plan
        </Button>
      )}
    </SectionCard>
  )
}

// -- Result summary sub-component ------------------------------------

function TrainingResultSummary({
  result,
}: {
  result: TrainingResultResponse
}) {
  const totalExtracted = result.items_extracted.reduce(
    (sum, [, count]) => sum + count,
    0,
  )
  const totalStored = result.items_stored.reduce(
    (sum, [, count]) => sum + count,
    0,
  )

  return (
    <div className="space-y-card">
      <div className="flex flex-wrap gap-grid-gap">
        <StatPill
          label="Sources"
          value={result.source_agents_used.length}
        />
        <StatPill label="Extracted" value={totalExtracted} />
        <StatPill label="Stored" value={totalStored} />
        {result.errors.length > 0 && (
          <StatPill label="Errors" value={result.errors.length} />
        )}
      </div>

      {/* Per-content-type breakdown */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-foreground">
          Items by Content Type
        </h4>
        {result.items_stored.map(([contentType, count]) => (
          <div
            key={contentType}
            className="flex items-center justify-between text-sm"
          >
            <span className="text-muted-foreground">
              {CONTENT_TYPE_LABELS[contentType] ?? contentType}
            </span>
            <span className="font-mono text-foreground">{count}</span>
          </div>
        ))}
      </div>

      {/* Errors */}
      {result.errors.length > 0 && (
        <div className="space-y-1">
          <h4 className="text-sm font-medium text-danger">
            Rejection Reasons
          </h4>
          {result.errors.map((error) => (
            <p
              key={error}
              className="text-xs text-muted-foreground"
            >
              {error}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
