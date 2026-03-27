import { cn } from '@/lib/utils'
import { formatCurrency } from '@/utils/format'

export interface TemplateCostBadgeProps {
  monthlyCost: number
  currency?: string
  className?: string
}

export function TemplateCostBadge({
  monthlyCost,
  currency = 'EUR',
  className,
}: TemplateCostBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-sm bg-accent/10 px-1.5 py-0.5',
        'font-mono text-xs font-medium text-accent',
        className,
      )}
      aria-label={`Estimated monthly cost: ${formatCurrency(monthlyCost, currency)}`}
    >
      ~{formatCurrency(monthlyCost, currency)}/mo
    </span>
  )
}
