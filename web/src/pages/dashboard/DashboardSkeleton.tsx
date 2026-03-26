import { SkeletonCard, SkeletonMetric } from '@/components/ui/skeleton'

export function DashboardSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-live="polite" aria-label="Loading dashboard">
      <div
        className="grid grid-cols-4 gap-grid-gap max-[1023px]:grid-cols-2"
        data-testid="skeleton-metrics-row"
      >
        <SkeletonMetric />
        <SkeletonMetric />
        <SkeletonMetric />
        <SkeletonMetric />
      </div>
      <div
        className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1"
        data-testid="skeleton-sections-row"
      >
        <SkeletonCard header lines={4} />
        <SkeletonCard header lines={4} />
      </div>
      <SkeletonCard header lines={3} data-testid="skeleton-chart" />
    </div>
  )
}
