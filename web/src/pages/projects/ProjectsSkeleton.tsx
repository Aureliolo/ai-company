import { Skeleton, SkeletonCard } from '@/components/ui/skeleton'

export function ProjectsSkeleton() {
  return (
    <div className="space-y-section-gap">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-8 w-36" />
      </div>
      <Skeleton className="h-10 w-full" />
      <div className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  )
}
