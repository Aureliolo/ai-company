/**
 * Entity definition card for the catalog grid.
 */
import { cn } from '@/lib/utils'
import type { EntityResponse } from '@/api/endpoints/ontology'

const TIER_STYLES = {
  core: 'bg-accent/10 text-accent border-accent/20',
  user: 'bg-success/10 text-success border-success/20',
} as const

const SOURCE_LABELS = {
  auto: 'Auto',
  config: 'Config',
  api: 'API',
} as const

interface EntityCardProps {
  entity: EntityResponse
  onClick?: () => void
}

export function EntityCard({ entity, onClick }: EntityCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full flex-col gap-2 rounded-lg border border-border bg-card p-card text-left',
        'transition-colors hover:border-bright hover:bg-card-hover',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
      )}
      aria-label={`View entity: ${entity.name}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          {entity.name}
        </h3>
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              'rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase',
              TIER_STYLES[entity.tier],
            )}
          >
            {entity.tier}
          </span>
          <span className="text-[10px] text-muted-foreground">
            {SOURCE_LABELS[entity.source]}
          </span>
        </div>
      </div>

      {/* Definition */}
      {entity.definition && (
        <p className="line-clamp-2 text-xs text-text-secondary">
          {entity.definition}
        </p>
      )}

      {/* Meta row */}
      <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
        {entity.fields.length > 0 && (
          <span>{entity.fields.length} fields</span>
        )}
        {entity.relationships.length > 0 && (
          <span>{entity.relationships.length} relations</span>
        )}
        {entity.constraints.length > 0 && (
          <span>{entity.constraints.length} constraints</span>
        )}
      </div>
    </button>
  )
}
