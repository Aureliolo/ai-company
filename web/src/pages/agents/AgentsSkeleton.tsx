import { Skeleton, SkeletonCard } from '@/components/ui/skeleton'

export function AgentsSkeleton() {
  return (
    <div className="space-y-section-gap">
      <Skeleton className="h-7 w-24" />
      <Skeleton className="h-10 w-full max-w-sm" />
      <div className="grid grid-cols-4 gap-grid-gap max-[1279px]:grid-cols-3 max-[1023px]:grid-cols-2">
        {Array.from({ length: 8 }, (_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  )
}
