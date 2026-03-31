import { Skeleton, SkeletonCard, SkeletonMetric } from '@/components/ui/skeleton'

export function AgentDetailSkeleton() {
  return (
    <div className="space-y-section-gap">
      {/* Identity header */}
      <div className="flex items-start gap-4">
        <Skeleton className="size-10 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-32" />
          <div className="flex gap-2">
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-5 w-24" />
          </div>
        </div>
      </div>

      {/* Prose placeholder */}
      <Skeleton className="h-16 w-full rounded-lg" />

      {/* Performance metrics 2x2 */}
      <SkeletonCard header lines={0} />
      <div className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
        <SkeletonMetric />
        <SkeletonMetric />
        <SkeletonMetric />
        <SkeletonMetric />
      </div>

      {/* Tools */}
      <SkeletonCard header lines={1} />

      {/* Two column: Timeline + Task History */}
      <div className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
        <SkeletonCard header lines={5} />
        <SkeletonCard header lines={5} />
      </div>

      {/* Activity log */}
      <SkeletonCard header lines={4} />
    </div>
  )
}
