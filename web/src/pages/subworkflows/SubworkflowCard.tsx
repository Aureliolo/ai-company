import { Layers, GitBranch, ArrowRightLeft } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SubworkflowSummary } from '@/api/types'

interface SubworkflowCardProps {
  subworkflow: SubworkflowSummary
  onClick: (subworkflow: SubworkflowSummary) => void
}

export function SubworkflowCard({ subworkflow, onClick }: SubworkflowCardProps) {
  return (
    <button
      type="button"
      className={cn(
        'flex w-full flex-col gap-2 rounded-lg border border-border bg-card p-card text-left',
        'transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
      )}
      onClick={() => onClick(subworkflow)}
      aria-label={`Subworkflow: ${subworkflow.name}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Layers className="size-4 text-accent" aria-hidden="true" />
          <span className="font-sans text-sm font-semibold text-foreground">
            {subworkflow.name}
          </span>
        </div>
        <span className="shrink-0 rounded-md bg-accent/10 px-1.5 py-0.5 text-xs font-medium text-accent">
          v{subworkflow.latest_version}
        </span>
      </div>

      {subworkflow.description && (
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {subworkflow.description}
        </p>
      )}

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1" title="Inputs">
          <ArrowRightLeft className="size-3" aria-hidden="true" />
          {subworkflow.input_count}in / {subworkflow.output_count}out
        </span>
        <span className="flex items-center gap-1" title="Versions">
          <GitBranch className="size-3" aria-hidden="true" />
          {subworkflow.version_count} version{subworkflow.version_count !== 1 ? 's' : ''}
        </span>
      </div>
    </button>
  )
}
