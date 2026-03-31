import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface MetadataGridItem {
  label: string
  value: ReactNode
  valueClassName?: string
}

export interface MetadataGridProps {
  items: readonly MetadataGridItem[]
  columns?: 2 | 3 | 4
  className?: string
}

export function MetadataGrid({ items, columns = 3, className }: MetadataGridProps) {
  const colClass =
    columns === 2
      ? 'grid-cols-2'
      : columns === 4
        ? 'grid-cols-4 max-[1023px]:grid-cols-2'
        : 'grid-cols-3 max-[1023px]:grid-cols-2'

  return (
    <dl
      className={cn(
        'grid gap-grid-gap rounded-lg border border-border p-card text-sm',
        colClass,
        className,
      )}
    >
      {items.map((item) => (
        <div key={item.label}>
          <dt className="text-[10px] uppercase tracking-wide text-text-muted">
            {item.label}
          </dt>
          <dd className={cn('text-foreground', item.valueClassName)}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}
