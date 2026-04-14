import { EmptyState } from '@/components/ui/empty-state'
import { Shield } from 'lucide-react'

export function MetaRuleStatus() {
  // Placeholder: real implementation fetches from /api/meta/rules.
  return (
    <EmptyState
      icon={Shield}
      title="No Rule Data"
      description="Rule firing status will appear here when rules are configured."
    />
  )
}
