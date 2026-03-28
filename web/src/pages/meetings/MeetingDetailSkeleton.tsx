import { Skeleton, SkeletonCard } from '@/components/ui/skeleton'

export function MeetingDetailSkeleton() {
  return (
    <div className="space-y-6" aria-label="Loading meeting detail">
      {/* Header */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Skeleton className="size-8 rounded" />
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-5 w-24 rounded-full" />
        </div>
        <div className="flex gap-3">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-7 w-28 rounded" />
          ))}
        </div>
      </div>

      {/* Agenda */}
      <SkeletonCard header lines={4} />

      {/* Token breakdown */}
      <SkeletonCard header lines={5} />

      {/* Contributions */}
      <SkeletonCard header lines={6} />

      {/* Decisions + Action Items */}
      <div className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
        <SkeletonCard header lines={3} />
        <SkeletonCard header lines={3} />
      </div>
    </div>
  )
}
