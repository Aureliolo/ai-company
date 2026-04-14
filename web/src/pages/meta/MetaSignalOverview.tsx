import { EmptyState } from '@/components/ui/empty-state'
import { Activity } from 'lucide-react'

export function MetaSignalOverview() {
  // Placeholder: real implementation fetches from /api/meta/signals.
  return (
    <EmptyState
      icon={Activity}
      title="No Signal Data"
      description="Signal data will appear here when the meta-loop runs its first cycle."
    />
  )
}
