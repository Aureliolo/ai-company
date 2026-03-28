import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { StatPill } from '@/components/ui/stat-pill'
import type { TemplateInfoResponse } from '@/api/types'
import { deriveCategoryFromTags, getCategoryLabel } from '@/utils/template-categories'

export interface TemplateCardProps {
  template: TemplateInfoResponse
  selected: boolean
  compared: boolean
  recommended?: boolean
  onSelect: () => void
  onToggleCompare: () => void
  compareDisabled: boolean
}

export function TemplateCard({
  template,
  selected,
  compared,
  recommended,
  onSelect,
  onToggleCompare,
  compareDisabled,
}: TemplateCardProps) {
  const category = getCategoryLabel(deriveCategoryFromTags(template.tags))

  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-lg border bg-card p-4 transition-colors',
        selected ? 'border-accent shadow-[0_0_12px_color-mix(in_srgb,var(--so-accent)_15%,transparent)]' : 'border-border',
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
          aria-label={`Compare ${template.display_name}`}
        />
        Compare
      </label>

      {/* Name + category + recommended */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-foreground">{template.display_name}</h3>
          {recommended && (
            <span className="inline-flex items-center rounded-full bg-accent/10 px-2 py-0.5 text-compact font-medium text-accent">
              Recommended
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <StatPill label="" value={category} className="text-compact" />
        </div>
        <p className="line-clamp-2 text-xs text-muted-foreground">{template.description}</p>
      </div>

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
