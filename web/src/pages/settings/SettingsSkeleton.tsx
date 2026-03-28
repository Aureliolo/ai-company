import { SkeletonCard } from '@/components/ui/skeleton'

export function SettingsSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-live="polite" aria-label="Loading settings">
      <div className="flex items-center justify-between">
        <div className="h-7 w-24 rounded bg-border" />
        <div className="h-9 w-64 rounded bg-border" />
      </div>
      <SkeletonCard header lines={5} />
      <SkeletonCard header lines={4} />
      <SkeletonCard header lines={3} />
      <SkeletonCard header lines={4} />
    </div>
  )
}
