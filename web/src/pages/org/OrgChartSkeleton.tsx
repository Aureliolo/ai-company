import { SkeletonCard } from '@/components/ui/skeleton'

export function OrgChartSkeleton() {
  return (
    <div
      className="flex h-full flex-col items-center gap-6 pt-12"
      role="status"
      aria-live="polite"
      aria-label="Loading org chart"
    >
      {/* CEO skeleton */}
      <SkeletonCard className="h-20 w-48" />

      {/* Department heads row */}
      <div className="flex gap-8">
        <SkeletonCard className="h-16 w-40" />
        <SkeletonCard className="h-16 w-40" />
        <SkeletonCard className="h-16 w-40" />
      </div>

      {/* Team members row */}
      <div className="flex gap-6">
        <SkeletonCard className="h-14 w-36" />
        <SkeletonCard className="h-14 w-36" />
        <SkeletonCard className="h-14 w-36" />
        <SkeletonCard className="h-14 w-36" />
      </div>
    </div>
  )
}
