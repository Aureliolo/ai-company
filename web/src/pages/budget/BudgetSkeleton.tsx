import {
  SkeletonCard,
  SkeletonMetric,
  SkeletonTable,
} from '@/components/ui/skeleton'

export function BudgetSkeleton() {
  return (
    <div
      className="space-y-section-gap"
      role="status"
      aria-live="polite"
      aria-label="Loading budget"
    >
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
        className="grid grid-cols-3 gap-grid-gap max-[1023px]:grid-cols-1"
        data-testid="skeleton-gauge-chart-row"
      >
        <SkeletonCard header lines={1} />
        <SkeletonCard header lines={3} className="col-span-2 max-[1023px]:col-span-1" />
      </div>
      <div
        className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1"
        data-testid="skeleton-breakdown-row"
      >
        <SkeletonCard header lines={3} />
        <SkeletonCard header lines={3} />
      </div>
      <SkeletonTable rows={5} columns={5} />
      <SkeletonCard header lines={4} />
    </div>
  )
}
