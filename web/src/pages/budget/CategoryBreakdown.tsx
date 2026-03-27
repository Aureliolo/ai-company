import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { formatCurrency } from '@/utils/format'
import { Layers } from 'lucide-react'
import type { CategoryRatio } from '@/utils/budget'

export interface CategoryBreakdownProps {
  ratio: CategoryRatio
  currency?: string
}

const CATEGORIES: {
  key: keyof CategoryRatio
  label: string
  barClass: string
  dotClass: string
}[] = [
  { key: 'productive', label: 'Productive', barClass: 'bg-success', dotClass: 'bg-success' },
  { key: 'coordination', label: 'Coordination', barClass: 'bg-accent', dotClass: 'bg-accent' },
  { key: 'system', label: 'System', barClass: 'bg-warning', dotClass: 'bg-warning' },
  { key: 'uncategorized', label: 'Uncategorized', barClass: 'bg-border', dotClass: 'bg-border' },
]

function isAllZero(ratio: CategoryRatio): boolean {
  return (
    ratio.productive.cost === 0 &&
    ratio.coordination.cost === 0 &&
    ratio.system.cost === 0 &&
    ratio.uncategorized.cost === 0
  )
}

export function CategoryBreakdown({ ratio, currency }: CategoryBreakdownProps) {
  const empty = isAllZero(ratio)

  return (
    <SectionCard title="Cost Categories" icon={Layers}>
      {empty ? (
        <EmptyState
          icon={Layers}
          title="No cost data"
          description="Category breakdown will appear as agents consume tokens"
        />
      ) : (
        <div className="space-y-4">
          {/* Stacked bar */}
          <div className="flex h-6 w-full overflow-hidden rounded-full">
            {CATEGORIES.map((cat) => (
              <div
                key={cat.key}
                style={{ width: `${ratio[cat.key].percent}%` }}
                className={`${cat.barClass} transition-all duration-500`}
                data-testid={`bar-${cat.key}`}
              />
            ))}
          </div>

          {/* Legend */}
          <div className="grid grid-cols-2 gap-3">
            {CATEGORIES.map((cat) => {
              const bucket = ratio[cat.key]
              return (
                <div key={cat.key} className="flex items-center gap-2">
                  <span className={`size-2 shrink-0 rounded-full ${cat.dotClass}`} />
                  <span className="text-xs text-text-secondary">{cat.label}</span>
                  <span className="ml-auto font-mono text-xs text-foreground">
                    {formatCurrency(bucket.cost, currency)}
                  </span>
                  <span className="font-mono text-[10px] text-text-muted">
                    {bucket.percent.toFixed(1)}%
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </SectionCard>
  )
}
