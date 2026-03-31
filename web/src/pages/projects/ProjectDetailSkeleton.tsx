import { Skeleton, SkeletonCard } from '@/components/ui/skeleton'

export function ProjectDetailSkeleton() {
  return (
    <div className="space-y-section-gap">
      <Skeleton className="h-8 w-32" />
      <SkeletonCard className="h-48" />
      <div className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
        <SkeletonCard className="h-40" />
        <SkeletonCard className="h-40" />
      </div>
    </div>
  )
}
