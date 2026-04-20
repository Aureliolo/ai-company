import { Package } from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { ArtifactCard } from './ArtifactCard'
import type { Artifact } from '@/api/types/artifacts'

interface ArtifactGridViewProps {
  artifacts: readonly Artifact[]
}

export function ArtifactGridView({ artifacts }: ArtifactGridViewProps) {
  if (artifacts.length === 0) {
    return (
      <EmptyState
        icon={Package}
        title="No artifacts found"
        description="Try adjusting your filters or search query."
      />
    )
  }

  return (
    <StaggerGroup className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 xl:grid-cols-3">
      {artifacts.map((artifact) => (
        <StaggerItem key={artifact.id}>
          <ArtifactCard artifact={artifact} />
        </StaggerItem>
      ))}
    </StaggerGroup>
  )
}
