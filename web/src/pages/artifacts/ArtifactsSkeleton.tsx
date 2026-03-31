import { Skeleton, SkeletonCard } from '@/components/ui/skeleton'

export function ArtifactsSkeleton() {
  return (
    <div className="space-y-section-gap">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-4 w-16" />
      </div>
      <Skeleton className="h-10 w-full" />
      <div className="grid grid-cols-3 gap-grid-gap max-[1279px]:grid-cols-2 max-[767px]:grid-cols-1">
        {Array.from({ length: 6 }, (_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  )
}
