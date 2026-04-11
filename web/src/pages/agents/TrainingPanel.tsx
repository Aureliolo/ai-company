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

import type { ReactNode } from 'react'
import { useCallback, useMemo, useState } from 'react'

import { GraduationCap } from 'lucide-react'

import { SectionCard } from '@/components/ui/section-card'
import { StatPill } from '@/components/ui/stat-pill'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { ToggleField } from '@/components/ui/toggle-field'
import { TagInput } from '@/components/ui/tag-input'
import { cn } from '@/lib/utils'
import { createLogger } from '@/lib/logger'
import { sanitizeForLog } from '@/utils/logging'
import type {
  TrainingPlanResponse,
  TrainingResultResponse,
} from '@/api/endpoints/training'

const log = createLogger('training-panel')

// -- Types -----------------------------------------------------------

/** Content types supported by the training pipeline. */
const TRAINING_CONTENT_TYPES = [
  'procedural',
  'semantic',
  'tool_patterns',
] as const

type TrainingContentType = (typeof TRAINING_CONTENT_TYPES)[number]

interface CustomCap {
  contentType: TrainingContentType
  cap: number
}

interface CreatePlanOverrides {
  override_sources: string[]
  content_types?: string[]
  custom_caps?: Record<string, number>
  skip_training: boolean
  require_review: boolean
}

interface TrainingPanelProps {
  agentName: string
  plan?: TrainingPlanResponse | null
  result?: TrainingResultResponse | null
  onCreatePlan?: (overrides: CreatePlanOverrides) => void
  onExecute?: () => void
  className?: string
}

// -- Content type labels ---------------------------------------------

const CONTENT_TYPE_LABELS: Record<TrainingContentType, string> = {
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
  const [enabledContentTypes, setEnabledContentTypes] = useState<
    Set<TrainingContentType>
  >(() => new Set(TRAINING_CONTENT_TYPES))
  const [customCaps, setCustomCaps] = useState<CustomCap[]>([])
  const [skipTraining, setSkipTraining] = useState(false)
  const [requireReview, setRequireReview] = useState(true)

  const toggleContentType = useCallback((ct: TrainingContentType) => {
    setEnabledContentTypes((prev) => {
      const next = new Set(prev)
      if (next.has(ct)) {
        next.delete(ct)
      } else {
        next.add(ct)
      }
      return next
    })
  }, [])

  const updateCap = useCallback(
    (ct: TrainingContentType, value: string) => {
      setCustomCaps((prev) => {
        const filtered = prev.filter((entry) => entry.contentType !== ct)
        if (!/^\d+$/.test(value)) {
          return filtered
        }
        const parsed = Number.parseInt(value, 10)
        if (parsed <= 0) {
          return filtered
        }
        return [...filtered, { contentType: ct, cap: parsed }]
      })
    },
    [],
  )

  const capsByType = useMemo(() => {
    const map = new Map<TrainingContentType, number>()
    for (const entry of customCaps) {
      map.set(entry.contentType, entry.cap)
    }
    return map
  }, [customCaps])

  const handleCreatePlan = () => {
    log.debug('Creating training plan', {
      agentName: sanitizeForLog(agentName),
      sourceCount: overrideSources.length,
      contentTypes: Array.from(enabledContentTypes),
    })
    const contentTypes = Array.from(enabledContentTypes)
    const customCapsPayload = customCaps.length
      ? Object.fromEntries(
          customCaps.map(({ contentType, cap }) => [contentType, cap]),
        )
      : undefined

    onCreatePlan?.({
      override_sources: overrideSources,
      content_types: contentTypes.length > 0 ? contentTypes : undefined,
      custom_caps: customCapsPayload,
      skip_training: skipTraining,
      require_review: requireReview,
    })
  }

  const canCreatePlan = skipTraining || enabledContentTypes.size > 0

  return (
    <SectionCard
      title="Training Mode"
      icon={GraduationCap}
      className={cn(className)}
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
      {result && <TrainingResultSummary result={result} />}

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

          <div>
            <span className="mb-1 block text-sm font-medium text-foreground">
              Content Types
            </span>
            <div className="space-y-2">
              {TRAINING_CONTENT_TYPES.map((ct) => (
                <ToggleField
                  key={ct}
                  label={CONTENT_TYPE_LABELS[ct]}
                  checked={enabledContentTypes.has(ct)}
                  onChange={() => toggleContentType(ct)}
                />
              ))}
            </div>
          </div>

          <div>
            <span className="mb-1 block text-sm font-medium text-foreground">
              Volume Caps (blank = default)
            </span>
            <div className="space-y-2">
              {TRAINING_CONTENT_TYPES.map((ct) => (
                <InputField
                  key={ct}
                  label={CONTENT_TYPE_LABELS[ct]}
                  type="number"
                  min={1}
                  value={capsByType.get(ct)?.toString() ?? ''}
                  onChange={(event) => updateCap(ct, event.target.value)}
                  placeholder="Use default"
                />
              ))}
            </div>
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

          <Button onClick={handleCreatePlan} disabled={!canCreatePlan}>
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
}): ReactNode {
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
        <StatPill label="Sources" value={result.source_agents_used.length} />
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
              {CONTENT_TYPE_LABELS[contentType as TrainingContentType] ??
                contentType}
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
          {result.errors.map((error, idx) => (
            // eslint-disable-next-line @eslint-react/no-array-index-key -- errors can repeat
            <p key={idx} className="text-xs text-muted-foreground">
              {error}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
