import { SkeletonCard } from '@/components/ui/skeleton'

export function ProvidersSkeleton() {
  return (
    <div
      className="grid grid-cols-3 gap-grid-gap max-[1023px]:grid-cols-2 max-[767px]:grid-cols-1"
      aria-label="Loading providers"
    >
      {Array.from({ length: 6 }, (_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  )
}
