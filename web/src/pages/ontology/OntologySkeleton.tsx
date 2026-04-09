/**
 * Loading skeleton for the ontology page.
 */
import { SkeletonCard, SkeletonText } from '@/components/ui/skeleton'

export function OntologySkeleton() {
  return (
    <div className="space-y-section-gap">
      <SkeletonText className="h-6 w-32" />
      <div className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <SkeletonCard key={i} className="h-40" />
        ))}
      </div>
      <SkeletonText className="h-6 w-40" />
      <SkeletonCard className="h-48" />
    </div>
  )
}
