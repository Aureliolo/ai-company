import { Skeleton, SkeletonCard, SkeletonMetric } from '@/components/ui/skeleton'

export function MeetingsSkeleton() {
  return (
    <div className="space-y-6" aria-label="Loading meetings">
      {/* Header */}
      <Skeleton className="h-7 w-32" />

      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-grid-gap lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <SkeletonMetric key={i} />
        ))}
      </div>

      {/* Timeline placeholder */}
      <div className="flex gap-3 overflow-hidden">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-20 w-36 shrink-0 rounded-lg" />
        ))}
      </div>

      {/* Card list */}
      <div className="space-y-3">
        {Array.from({ length: 5 }, (_, i) => (
          <SkeletonCard key={i} lines={3} />
        ))}
      </div>
    </div>
  )
}
