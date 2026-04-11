import { SkeletonCard, SkeletonMetric } from '@/components/ui/skeleton'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'

export function ScalingSkeleton() {
  return (
    <div className="flex flex-col gap-section-gap p-6">
      <StaggerGroup className="grid grid-cols-4 gap-card-gap">
        {(['strategies', 'decisions', 'utilization', 'budget'] as const).map(
          (id) => (
            <StaggerItem key={id}>
              <SkeletonMetric />
            </StaggerItem>
          ),
        )}
      </StaggerGroup>
      <div className="grid grid-cols-2 gap-card-gap">
        <SkeletonCard className="h-64" />
        <SkeletonCard className="h-64" />
      </div>
      <SkeletonCard className="h-96" />
    </div>
  )
}
