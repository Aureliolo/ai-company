import { Package } from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { ArtifactCard } from './ArtifactCard'
import type { Artifact } from '@/api/types'

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
    <StaggerGroup className="grid grid-cols-3 gap-grid-gap max-[1279px]:grid-cols-2 max-[767px]:grid-cols-1">
      {artifacts.map((artifact) => (
        <StaggerItem key={artifact.id}>
          <ArtifactCard artifact={artifact} />
        </StaggerItem>
      ))}
    </StaggerGroup>
  )
}
