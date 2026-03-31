import { Skeleton, SkeletonCard } from '@/components/ui/skeleton'

export function ArtifactDetailSkeleton() {
  return (
    <div className="space-y-section-gap">
      <Skeleton className="h-8 w-32" />
      <SkeletonCard className="h-48" />
      <SkeletonCard className="h-64" />
    </div>
  )
}
