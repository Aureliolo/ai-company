import { Drawer } from '@/components/ui/drawer'
import { Button } from '@/components/ui/button'
import { StatPill } from '@/components/ui/stat-pill'
import type { TemplateInfoResponse } from '@/api/types'
import { TemplateCostBadge } from './TemplateCostBadge'

export interface TemplateCompareDrawerProps {
  open: boolean
  onClose: () => void
  templates: readonly TemplateInfoResponse[]
  estimatedCosts: ReadonlyMap<string, number>
  currency: string
  onSelect: (name: string) => void
  onRemove: (name: string) => void
}

const COMPARISON_ROWS = [
  { label: 'Source', key: 'source' },
  { label: 'Tags', key: 'tags' },
  { label: 'Skill Patterns', key: 'skill_patterns' },
] as const

export function TemplateCompareDrawer({
  open,
  onClose,
  templates,
  estimatedCosts,
  currency,
  onSelect,
  onRemove,
}: TemplateCompareDrawerProps) {
  if (templates.length < 2) return null

  return (
    <Drawer open={open} onClose={onClose} title="Compare Templates">
      <div className="space-y-4">
        {/* Column headers */}
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${templates.length}, 1fr)` }}>
          {templates.map((t) => (
            <div key={t.name} className="space-y-2 rounded-md border border-border p-3">
              <h3 className="text-sm font-semibold text-foreground">{t.display_name}</h3>
              <p className="text-xs text-muted-foreground line-clamp-3">{t.description}</p>
              <TemplateCostBadge monthlyCost={estimatedCosts.get(t.name) ?? 0} currency={currency} />
            </div>
          ))}
        </div>

        {/* Comparison rows */}
        {COMPARISON_ROWS.map((row) => (
          <div key={row.key}>
            <h4 className="mb-1 text-compact uppercase tracking-wide text-muted-foreground">
              {row.label}
            </h4>
            <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${templates.length}, 1fr)` }}>
              {templates.map((t) => {
                const value = t[row.key]
                const display = Array.isArray(value) ? value.join(', ') : String(value)
                return (
                  <div key={t.name} className="text-xs text-foreground">
                    {row.key === 'tags' ? (
                      <div className="flex flex-wrap gap-1">
                        {(value as readonly string[]).map((tag) => (
                          <StatPill key={tag} label="" value={tag} className="text-compact" />
                        ))}
                      </div>
                    ) : (
                      display || '--'
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}

        {/* Action buttons */}
        <div className="grid gap-4 border-t border-border pt-4" style={{ gridTemplateColumns: `repeat(${templates.length}, 1fr)` }}>
          {templates.map((t) => (
            <div key={t.name} className="flex flex-col gap-2">
              <Button size="sm" onClick={() => onSelect(t.name)}>Select</Button>
              <Button variant="ghost" size="sm" onClick={() => onRemove(t.name)}>
                Remove
              </Button>
            </div>
          ))}
        </div>
      </div>
    </Drawer>
  )
}
