import { SkeletonCard } from '@/components/ui/skeleton'

const PLACEHOLDER_KEYS = ['a', 'b', 'c', 'd', 'e', 'f'] as const

export function ConnectionsSkeleton() {
  return (
    <div className="grid grid-cols-3 gap-grid-gap max-[1023px]:grid-cols-2 max-[767px]:grid-cols-1">
      {PLACEHOLDER_KEYS.map((key) => (
        <SkeletonCard key={key} />
      ))}
    </div>
  )
}
