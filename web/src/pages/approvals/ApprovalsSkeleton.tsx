import { Skeleton, SkeletonCard, SkeletonMetric } from '@/components/ui/skeleton'

export function ApprovalsSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading approvals">
      {/* Filter bar skeleton */}
      <div className="flex items-center gap-3">
        <Skeleton className="h-8 w-28 rounded-md" />
        <Skeleton className="h-8 w-28 rounded-md" />
        <Skeleton className="h-8 w-28 rounded-md" />
        <Skeleton className="h-8 flex-1 max-w-xs rounded-md" />
      </div>

      {/* Metric cards skeleton */}
      <div className="grid grid-cols-4 gap-grid-gap max-[1023px]:grid-cols-2">
        <SkeletonMetric />
        <SkeletonMetric />
        <SkeletonMetric />
        <SkeletonMetric />
      </div>

      {/* Risk group sections skeleton */}
      <SkeletonCard header lines={3} />
      <SkeletonCard header lines={2} />
      <SkeletonCard header lines={1} />
    </div>
  )
}
