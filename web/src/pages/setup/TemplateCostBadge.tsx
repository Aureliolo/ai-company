import { cn } from '@/lib/utils'
import { formatCurrency } from '@/utils/format'
import type { CurrencyCode } from '@/utils/currencies'
import { DEFAULT_CURRENCY } from '@/utils/currencies'

export interface TemplateCostBadgeProps {
  monthlyCost: number
  currency?: CurrencyCode
  className?: string
}

export function TemplateCostBadge({
  monthlyCost,
  currency = DEFAULT_CURRENCY,
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
