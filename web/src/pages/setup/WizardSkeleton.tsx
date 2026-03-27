import { Skeleton, SkeletonCard, SkeletonText } from '@/components/ui/skeleton'

export function WizardSkeleton() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-start bg-background pt-16">
      <div className="w-full max-w-4xl space-y-8 px-4">
        {/* Progress bar skeleton */}
        <div className="flex items-center justify-center gap-4">
          {Array.from({ length: 7 }, (_, i) => (
            <div key={i} className="flex flex-col items-center gap-1">
              <Skeleton className="size-8 rounded-full" />
              <Skeleton className="h-3 w-12" />
            </div>
          ))}
        </div>

        {/* Content skeleton */}
        <div className="space-y-6">
          <Skeleton className="h-6 w-48" />
          <SkeletonText lines={2} />
          <SkeletonCard />
          <SkeletonCard />
        </div>

        {/* Navigation skeleton */}
        <div className="flex justify-between border-t border-border pt-4">
          <Skeleton className="h-9 w-20" />
          <Skeleton className="h-9 w-20" />
        </div>
      </div>
    </div>
  )
}
