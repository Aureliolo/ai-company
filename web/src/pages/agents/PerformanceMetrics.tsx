import { MetricCard } from '@/components/ui/metric-card'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { SectionCard } from '@/components/ui/section-card'
import { BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { MetricCardProps } from '@/components/ui/metric-card'

interface PerformanceMetricsProps {
  cards: Omit<MetricCardProps, 'className'>[]
  className?: string
}

export function PerformanceMetrics({ cards, className }: PerformanceMetricsProps) {
  if (cards.length === 0) return null

  return (
    <SectionCard title="Performance" icon={BarChart3} className={className}>
      <StaggerGroup
        className={cn('grid grid-cols-1 gap-grid-gap md:grid-cols-2 lg:grid-cols-4')}
      >
        {cards.map((card) => (
          <StaggerItem key={card.label}>
            <MetricCard {...card} />
          </StaggerItem>
        ))}
      </StaggerGroup>
    </SectionCard>
  )
}
