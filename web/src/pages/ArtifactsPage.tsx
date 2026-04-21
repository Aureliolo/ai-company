import { useArtifactsData } from '@/hooks/useArtifactsData'
import { ErrorBanner } from '@/components/ui/error-banner'
import { ListHeader } from '@/components/ui/list-header'
import { ArtifactsSkeleton } from './artifacts/ArtifactsSkeleton'
import { ArtifactFilters } from './artifacts/ArtifactFilters'
import { ArtifactGridView } from './artifacts/ArtifactGridView'

export default function ArtifactsPage() {
  const {
    filteredArtifacts,
    totalArtifacts,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useArtifactsData()

  if (loading && totalArtifacts === 0) {
    return <ArtifactsSkeleton />
  }

  return (
    <div className="space-y-section-gap">
      <ListHeader
        title="Artifacts"
        count={filteredArtifacts.length}
        countLabel={filteredArtifacts.length === totalArtifacts ? undefined : `${filteredArtifacts.length} of ${totalArtifacts}`}
      />

      {error && (
        <ErrorBanner severity="error" title="Could not load artifacts" description={error} />
      )}

      {!wsConnected && !loading && (
        <ErrorBanner
          variant="offline"
          title="Real-time updates disconnected"
          description={wsSetupError ?? 'Data may be stale until the connection recovers.'}
        />
      )}

      <ArtifactFilters />
      <ArtifactGridView artifacts={filteredArtifacts} />
    </div>
  )
}
