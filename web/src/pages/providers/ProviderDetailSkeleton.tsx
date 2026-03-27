import { Skeleton, SkeletonMetric } from '@/components/ui/skeleton'
import { SectionCard } from '@/components/ui/section-card'
import { Boxes } from 'lucide-react'

export function ProviderDetailSkeleton() {
  return (
    <div className="flex flex-col gap-section-gap" aria-label="Loading provider details">
      {/* Header skeleton */}
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>

      {/* Metrics skeleton */}
      <div className="grid grid-cols-4 gap-grid-gap max-[1023px]:grid-cols-2">
        {Array.from({ length: 4 }, (_, i) => (
          <SkeletonMetric key={i} />
        ))}
      </div>

      {/* Model list skeleton */}
      <SectionCard title="Models" icon={Boxes}>
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-8 w-full mb-2" />
        ))}
      </SectionCard>
    </div>
  )
}
