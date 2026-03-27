import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { StatPill } from '@/components/ui/stat-pill'
import type { TemplateInfoResponse } from '@/api/types'
import { TemplateCostBadge } from './TemplateCostBadge'

export interface TemplateCardProps {
  template: TemplateInfoResponse
  estimatedCost: number
  currency: string
  selected: boolean
  compared: boolean
  onSelect: () => void
  onToggleCompare: () => void
  compareDisabled: boolean
}

export function TemplateCard({
  template,
  estimatedCost,
  currency,
  selected,
  compared,
  onSelect,
  onToggleCompare,
  compareDisabled,
}: TemplateCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-lg border bg-card p-4 transition-colors',
        selected ? 'border-accent shadow-[0_0_12px_var(--so-accent)/15%]' : 'border-border',
        'hover:bg-card-hover',
      )}
    >
      {/* Compare checkbox */}
      <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
        <input
          type="checkbox"
          checked={compared}
          onChange={onToggleCompare}
          disabled={compareDisabled && !compared}
          className="accent-accent"
        />
        Compare
      </label>

      {/* Name + description */}
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">{template.display_name}</h3>
        <p className="line-clamp-2 text-xs text-muted-foreground">{template.description}</p>
      </div>

      {/* Cost badge */}
      <TemplateCostBadge monthlyCost={estimatedCost} currency={currency} />

      {/* Tags */}
      <div className="flex flex-wrap gap-1">
        {template.tags.map((tag) => (
          <StatPill key={tag} label="" value={tag} className="text-compact" />
        ))}
      </div>

      {/* Select button */}
      <Button
        variant={selected ? 'default' : 'outline'}
        size="sm"
        onClick={onSelect}
        className="mt-auto"
      >
        {selected ? 'Selected' : 'Select'}
      </Button>
    </div>
  )
}
