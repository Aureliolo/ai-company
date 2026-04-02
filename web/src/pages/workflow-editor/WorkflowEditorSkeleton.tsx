import { Skeleton } from '@/components/ui/skeleton'

export function WorkflowEditorSkeleton() {
  return (
    <div className="flex h-full flex-col gap-3">
      {/* Toolbar skeleton */}
      <Skeleton className="h-10 w-full rounded-lg" />

      {/* Canvas skeleton */}
      <Skeleton className="flex-1 rounded-lg" />

      {/* YAML preview skeleton */}
      <Skeleton className="h-48 rounded-lg" />
    </div>
  )
}
